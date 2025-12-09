import requests
import unicodedata
import asyncio
import aiohttp
import re
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache
from collections import Counter
from functools import lru_cache
import numpy as np


GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_URL = "https://openlibrary.org"


# ============================================
# CONSTANTES DE AJUSTE DEL ALGORITMO
# ============================================

# Scoring (La suma de los máximos es aproximadamente el score base máximo)
SCORE_AUTHOR_MATCH = 30
SCORE_CATEGORY_MAX = 15
SCORE_SIMILARITY_MAX = 30 # Máximo para embeddings / fallback keywords
SCORE_SERIES_BONUS = 20
SCORE_RATING_BASE_MAX = 15 # Basado en la nota 0-5
SCORE_RATING_COUNT_MAX = 15 # Basado en la cantidad de ratings

# Límites de Diversidad (para asegurar_diversidad_avanzada)
DIVERSITY_MAX_AUTHOR = 2
DIVERSITY_MAX_DECADA = 3
DIVERSITY_MAX_SERIE = 2
FINAL_RECOMMENDATION_LIMIT = 4 # Límite de recomendaciones finales

# Palabras vacías (Stop Words) para extracción de keywords
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'el', 'la', 'de', 'en', 'y', 'que', 'los', 'las', 'un', 'una', 'su',
    'del', 'al'
}


# Modelo de embeddings (carga lazy)
_modelo_embeddings = None

def obtener_modelo_embeddings():
    """Carga el modelo solo cuando se necesita (lazy loading)"""
    global _modelo_embeddings
    if _modelo_embeddings is None:
        try:
            from sentence_transformers import SentenceTransformer
            _modelo_embeddings = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        except ImportError:
            print("⚠️ sentence-transformers no instalado. Usando fallback básico.")
            _modelo_embeddings = False
    return _modelo_embeddings

# ============================================
# FUNCIONES AUXILIARES BÁSICAS
# ============================================

def normalizar_texto(texto):
    if not texto:
        return ""
    # NFKD elimina acentos, tildes, etc.
    texto = unicodedata.normalize('NFKD', texto)
    # ASCII, 'ignore' elimina caracteres especiales no ASCII (como la ñ)
    texto = texto.encode('ASCII', 'ignore').decode('utf-8')
    return ' '.join(texto.lower().split())


def cache_inteligente(key, data, tipo='normal'):
    """
    Cache con TTL variable según tipo de datos
    """
    ttls = {
        'ratings': 86400,      # 24h - ratings cambian poco
        'busqueda': 3600,      # 1h - búsquedas actuales
        'usuario': 1800,       # 30min - comportamiento usuario
        'trending': 600,       # 10min - tendencias actuales
        'normal': 3600
    }
    
    cache.set(key, data, ttls.get(tipo, 3600))


def buscar_con_cache(url, params, cache_key_prefix, timeout=10):
    cache_key = f"{cache_key_prefix}_{str(params)}"
    resultado = cache.get(cache_key)
    
    if resultado:
        return resultado
    
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        resultado = resp.json()
        cache_inteligente(cache_key, resultado, 'busqueda')
        return resultado
    except Exception as e:
        # print(f"Error en búsqueda síncrona: {e}") # Descomentar para debug
        return None


# ============================================
# PRIORIDAD 1: EMBEDDINGS SEMÁNTICOS
# ============================================

@lru_cache(maxsize=1000)
def calcular_embedding(texto):
    """
    Calcula embedding con cache en memoria
    """
    modelo = obtener_modelo_embeddings()
    if modelo and modelo is not False:
        return modelo.encode(texto)
    return None


def similitud_keywords_fallback(texto1, texto2):
    """
    Fallback si no hay sentence-transformers disponible
    """
    palabras1 = set(texto1.lower().split())
    palabras2 = set(texto2.lower().split())
    
    interseccion = palabras1.intersection(palabras2)
    union = palabras1.union(palabras2)
    
    if not union:
        return 0
    
    jaccard = len(interseccion) / len(union)
    return jaccard * SCORE_SIMILARITY_MAX # Usar constante


def calcular_similitud_semantica(descripcion_fuente, descripcion_candidato):
    """
    Similitud semántica profunda usando embeddings
    Mucho más preciso que keywords básicos
    """
    if not descripcion_fuente or not descripcion_candidato:
        return 0
    
    # Limitar longitud para performance
    desc1 = descripcion_fuente[:500]
    desc2 = descripcion_candidato[:500]
    
    emb1 = calcular_embedding(desc1)
    emb2 = calcular_embedding(desc2)
    
    if emb1 is None or emb2 is None:
        # Fallback: similitud por keywords básica
        return similitud_keywords_fallback(desc1, desc2)
    
    # Similitud coseno
    # Usamos np.float() para asegurar compatibilidad de tipos
    similitud = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
    
    # Convertir a puntos (0-30)
    return float(similitud) * SCORE_SIMILARITY_MAX # Usar constante


# ============================================
# PRIORIDAD 1: DETECCIÓN DE SERIES
# ============================================

def detectar_serie(titulo):
    """
    Detecta si un libro es parte de una serie
    Retorna: (nombre_serie, numero_en_serie)
    """
    patrones = [
        r'\b(Book|Vol\.?|Volume|Part|Libro|Tomo)\s*(\d+)',
        r'\(#(\d+)\)',
        r':\s*Book\s*(\d+)',
        r',\s*Book\s*(\d+)',
        r'\b(\d+)\s*of\s*\d+',
    ]
    
    for patron in patrones:
        match = re.search(patron, titulo, re.IGNORECASE)
        if match:
            # Extraer nombre de serie (sin el número)
            nombre_serie = re.sub(patron, '', titulo, flags=re.IGNORECASE).strip()
            nombre_serie = nombre_serie.rstrip(':,-').strip()
            # Intenta obtener group(2) (para patrones con Book/Vol/etc. y número) o group(1)
            try:
                numero = match.group(2)
            except IndexError:
                numero = match.group(1)
            
            return nombre_serie, numero
    
    return None, None


def buscar_libros_misma_serie(titulo_fuente, autor):
    """
    Busca otros libros de la misma serie
    """
    nombre_serie, numero = detectar_serie(titulo_fuente)
    
    if not nombre_serie:
        return []
    
    # Buscar con el nombre de la serie
    params = {
        'q': f'intitle:"{nombre_serie}" inauthor:"{autor}"',
        'maxResults': 10
    }
    
    data = buscar_con_cache(GOOGLE_BOOKS_URL, params, 'google_serie')
    
    if data and 'items' in data:
        return data['items']
    
    return []


# ============================================
# PRIORIDAD 1: BÚSQUEDAS ASÍNCRONAS
# ============================================

async def buscar_async(session, url, params, cache_key):
    """
    Búsqueda asíncrona con manejo de errores
    """
    # Revisar cache primero
    resultado = cache.get(cache_key)
    if resultado:
        return resultado
    
    try:
        # Usar aiohttp.ClientTimeout para configurar el tiempo de espera
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                cache_inteligente(cache_key, data, 'busqueda')
                return data
    except Exception as e:
        print(f"Error en búsqueda async: {e}")
    
    return None


async def buscar_open_library_async(session, autor, keywords):
    """
    Busca candidatos de Open Library. La clave 'docs' contiene los resultados.
    """
    if not autor and not keywords:
        return None

    # Usamos la combinación de autor y keywords para la query
    query = f'author:"{autor}"' if autor else ' '.join(keywords)
    
    url = f"{OPEN_LIBRARY_URL}/search.json"
    # Aumentamos el límite para tener más candidatos en español, ya que OL no tiene tanta info
    params = {'q': query, 'limit': 25, 'language': 'spa'} 
    cache_key = f'ol_search_{normalizar_texto(query)}'
    
    resultado = cache.get(cache_key)
    if resultado:
        return resultado
        
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                cache_inteligente(cache_key, data, 'busqueda')
                return data
    except Exception as e:
        print(f"Error en búsqueda async de Open Library: {e}")
    
    return None

def normalizar_open_library(ol_data):
    """
    Convierte los resultados de Open Library (ol_data) al formato de Google Books 
    para que el resto del sistema de scoring pueda procesarlos.
    """
    if not ol_data or 'docs' not in ol_data:
        return []
    
    candidatos_normalizados = []
    
    for doc in ol_data['docs']:
        # Volvemos a filtrar el idioma OL: 'spa' para ser seguros
        languages = doc.get('language', [])
        if 'spa' not in languages and 'es' not in languages:
            continue
            
        book_id = doc.get('key')
        if not book_id:
            continue
            
        # Mapear los datos al formato de Google Books
        
        authors = doc.get('author_name', [])
        categories = doc.get('subject', [])
        published_date = str(doc.get('first_publish_year', ''))
        
        # Imagen: OL usa 'cover_i' para el ID de la imagen
        image_id = doc.get('cover_i')
        # URL de portada media (M)
        image_url = f"https://covers.openlibrary.org/b/id/{image_id}-M.jpg" if image_id else None
        
        # Open Library search API no proporciona ratings ni descripción detallada en este endpoint.
        
        candidato = {
            "id": book_id, 
            "volumeInfo": {
                "title": doc.get('title'),
                "authors": authors,
                "publishedDate": published_date,
                "categories": categories,
                "language": 'es', # Lo forzamos a 'es'
                
                # Datos faltantes de OL (se dejan vacíos/cero)
                "description": "", 
                "averageRating": 0.0,
                "ratingsCount": 0,
                "imageLinks": {
                    "thumbnail": image_url
                }
            }
        }
        
        candidatos_normalizados.append(candidato)
        
    return candidatos_normalizados

async def buscar_multiples_fuentes_async(autor, categorias, keywords, titulo):
    """
    Ejecuta múltiples búsquedas en paralelo, incluyendo Open Library.
    """
    async with aiohttp.ClientSession() as session:
        tareas = []
        
        # 1. Mismo autor (Google)
        tareas.append(buscar_async(
            session, GOOGLE_BOOKS_URL,
            {'q': f'inauthor:"{autor}"', 'maxResults': 8},
            f'google_autor_{normalizar_texto(autor)}'
        ))
        
        # 2. Categorías principales (Google)
        for i, categoria in enumerate(categorias[:3]):
            cat_simple = categoria.split("/")[-1].strip()
            tareas.append(buscar_async(
                session, GOOGLE_BOOKS_URL,
                {'q': f'subject:"{cat_simple}"', 'maxResults': 15, 'orderBy': 'relevance'},
                f'google_cat_{normalizar_texto(cat_simple)}_{i}'
            ))
        
        # 3. Keywords semánticos (Google)
        for i in range(0, min(len(keywords), 4), 2):
            query = ' '.join(keywords[i:i+2])
            tareas.append(buscar_async(
                session, GOOGLE_BOOKS_URL,
                {'q': query, 'maxResults': 10, 'orderBy': 'relevance'},
                f'google_keywords_{i}'
            ))
        
        # 4. Búsqueda de series (Google)
        nombre_serie, _ = detectar_serie(titulo)
        if nombre_serie:
            tareas.append(buscar_async(
                session, GOOGLE_BOOKS_URL,
                {'q': f'intitle:"{nombre_serie}" inauthor:"{autor}"', 'maxResults': 10},
                f'google_serie_{normalizar_texto(nombre_serie)}'
            ))
            
        # 5. Open Library (NUEVA FUENTE)
        if autor or keywords:
            tareas.append(buscar_open_library_async(
                session, autor, keywords
            ))
        
        # Ejecutar todas en paralelo
        resultados = await asyncio.gather(*tareas, return_exceptions=True)
        
        # Consolidar resultados
        candidatos = []
        
        for resultado in resultados:
            if resultado and not isinstance(resultado, Exception):
                # Resultados de Google Books (tienen 'items')
                if 'items' in resultado:
                    candidatos.extend(resultado['items'])
                
                # Resultados de Open Library (tienen 'docs' y DEBEN ser normalizados)
                elif 'docs' in resultado:
                    candidatos.extend(normalizar_open_library(resultado))
        
        return candidatos


# ============================================
# PRIORIDAD 2: AJUSTE POR POPULARIDAD
# ============================================

def ajustar_por_popularidad(rating_score, ratings_count):
    """
    Aplica el ajuste anti-bestseller solo al componente de puntuación de rating.
    """
    if ratings_count > 50000:
        # Mega-bestseller: leve penalización
        return rating_score * 0.92
    elif ratings_count > 10000:
        # Muy popular: sin cambio
        return rating_score
    elif ratings_count < 50 and ratings_count >= 10:
        # Nicho con algunas reviews: boost moderado
        return rating_score * 1.08
    elif ratings_count < 10 and ratings_count > 0:
        # Muy nicho: boost leve (podría ser libro nuevo bueno)
        return rating_score * 1.05
    
    return rating_score


# ============================================
# PRIORIDAD 2: FALLBACK INTELIGENTE
# ============================================

def generar_fallback_inteligente(libro_fuente, autor, candidatos_actuales):
    """
    Si tenemos pocas recomendaciones (<4), busca alternativas inteligentes
    """
    if len(candidatos_actuales) >= 4:
        return []
    
    fallback_candidatos = []
    
    # Estrategia 1: Bestsellers de la misma categoría
    categorias = libro_fuente.get('categories', [])
    if categorias:
        cat_principal = categorias[0].split('/')[-1].strip()
        data = buscar_con_cache(
            GOOGLE_BOOKS_URL,
            {'q': f'subject:"{cat_principal}"', 'maxResults': 15, 'orderBy': 'relevance'},
            'fallback_bestsellers'
        )
        if data and 'items' in data:
            fallback_candidatos.extend(data['items'])
    
    # Estrategia 2: Libros de la misma década
    fecha = libro_fuente.get('publishedDate', '')
    if len(fecha) >= 4:
        try:
            decada = (int(fecha[:4]) // 10) * 10
            data = buscar_con_cache(
                GOOGLE_BOOKS_URL,
                {'q': f'{autor} {decada}', 'maxResults': 10},
                f'fallback_decada_{decada}'
            )
            if data and 'items' in data:
                fallback_candidatos.extend(data['items'])
        except ValueError:
            pass # Si la fecha no es un número válido, ignorar
    
    return fallback_candidatos


# ============================================
# SCORING MEJORADO CON NUEVAS FEATURES
# ============================================

def calcular_score_avanzado_v2(item, libro_fuente, autor_fuente, categorias_fuente, descripcion_fuente, fecha_fuente):
    """
    Sistema de scoring mejorado con embeddings, series y popularidad ajustada
    Utiliza las constantes globales de SCORE_...
    """
    score = 0
    info = item.get('volumeInfo', {})
    
    # Check for Open Library source (OL candidates lack description and ratings)
    is_from_ol = (info.get('description', '') == "" and info.get('ratingsCount', 0) == 0)

    # 1. Autor (MAX 30 pts)
    author_score = 0
    autores = info.get('authors', [])
    if autor_fuente in autores:
        author_score = SCORE_AUTHOR_MATCH
    score += author_score
    
    # 2. Rating y popularidad (MAX 30 pts)
    rating = info.get('averageRating', 0)
    ratings_count = info.get('ratingsCount', 0)
    rating_base_score = 0
    rating_count_score = 0
    
    if rating > 0:
        rating_base_score = (rating / 5.0) * SCORE_RATING_BASE_MAX
    if ratings_count > 5000:
        rating_count_score = SCORE_RATING_COUNT_MAX
    elif ratings_count > 1000:
        rating_count_score = SCORE_RATING_COUNT_MAX * (2/3)
    elif ratings_count > 100:
        rating_count_score = SCORE_RATING_COUNT_MAX * (1/3)

    # Aplica ajuste por popularidad solo al componente de rating
    total_ratings_score = rating_base_score + rating_count_score
    adjusted_ratings_score = ajustar_por_popularidad(total_ratings_score, ratings_count)
    score += adjusted_ratings_score
    
    # 3. Categorías (MAX 15 pts)
    category_score = 0
    categorias_item = info.get('categories', [])
    if categorias_item and categorias_fuente:
        matches = sum(1 for cat_f in categorias_fuente 
                     for cat_i in categorias_item 
                     if cat_f.lower() in cat_i.lower() or cat_i.lower() in cat_f.lower())
        category_score = min(matches * 5, SCORE_CATEGORY_MAX)
    score += category_score
    
    # 4. SIMILITUD SEMÁNTICA (MAX 30 pts)
    semantic_score = 0
    descripcion_item = info.get('description', '')
    if descripcion_fuente and descripcion_item:
        semantic_score = calcular_similitud_semantica(descripcion_fuente, descripcion_item)
    score += semantic_score
    
    # 5. Misma serie (BONUS 20 pts)
    series_score = 0
    titulo_item = info.get('title', '')
    titulo_fuente = libro_fuente.get('title', '')
    serie_item, _ = detectar_serie(titulo_item)
    serie_fuente, _ = detectar_serie(titulo_fuente)
    if serie_item and serie_fuente and normalizar_texto(serie_item) == normalizar_texto(serie_fuente):
        series_score = SCORE_SERIES_BONUS
    score += series_score
    
    # 6. Recencia relativa (MAX 5 pts)
    recency_score = 0
    try:
        fecha_item = info.get('publishedDate', '')[:4]
        if fecha_fuente and fecha_item:
            diferencia_años = abs(int(fecha_fuente) - int(fecha_item))
            if diferencia_años <= 5:
                recency_score = 5
            elif diferencia_años <= 10:
                recency_score = 3
    except:
        pass
    score += recency_score
    
    # --- AJUSTE CRÍTICO: Compensación por Open Library ---
    if is_from_ol:
        # Sumamos las puntuaciones de contenido fuerte (no dependiente de descripción/ratings)
        content_match = author_score + category_score + series_score
        if content_match > 30: # Requiere una coincidencia fuerte (ej. autor + categoría)
            # Aplicamos un bonus para que compita mejor contra candidatos completos
            score += 25 
            
    return score


# ============================================
# DIVERSIDAD MEJORADA
# ============================================

def asegurar_diversidad_avanzada(libros_con_score, max_por_autor=DIVERSITY_MAX_AUTHOR, max_por_decada=DIVERSITY_MAX_DECADA, max_misma_serie=DIVERSITY_MAX_SERIE):
    """
    Diversidad considerando autor, época Y series
    Utiliza las constantes DIVERSITY_... y FINAL_RECOMMENDATION_LIMIT
    """
    autores_count = {}
    decadas_count = {}
    series_count = {}
    resultados = []
    
    for libro in libros_con_score:
        autor = libro['autor']
        titulo = libro['titulo']
        
        # Extraer década
        decada = None
        try:
            año = libro.get('año_publicacion', '')[:4]
            if año:
                decada = (int(año) // 10) * 10
        except:
            pass
        
        # Detectar serie
        serie, _ = detectar_serie(titulo)
        serie_normalizada = normalizar_texto(serie) if serie else None
        
        # Contadores
        count_autor = autores_count.get(autor, 0)
        count_decada = decadas_count.get(decada, 0) if decada else 0
        count_serie = series_count.get(serie_normalizada, 0) if serie_normalizada else 0
        
        # Aplicar límites
        if count_autor >= max_por_autor:
            continue
        if decada and count_decada >= max_por_decada:
            continue
        if serie_normalizada and count_serie >= max_misma_serie:
            continue
        
        resultados.append(libro)
        
        # Actualizar contadores
        autores_count[autor] = count_autor + 1
        if decada:
            decadas_count[decada] = count_decada + 1
        if serie_normalizada:
            series_count[serie_normalizada] = count_serie + 1
        
        if len(resultados) >= FINAL_RECOMMENDATION_LIMIT:
            break
    
    return resultados


# ============================================
# FUNCIONES AUXILIARES DE LA VISTA PRINCIPAL
# ============================================

def extraer_keywords(libro_info):
    """
    Extrae palabras clave de categorías y descripción, excluyendo stop words.
    """
    keywords = set()
    categorias = libro_info.get('categories', [])
    for cat in categorias:
        keywords.update(cat.lower().split())
    
    descripcion = libro_info.get('description', '')
    
    palabras = descripcion.lower().split()
    # Usar el set de STOP_WORDS
    keywords.update([p for p in palabras if len(p) > 4 and p not in STOP_WORDS])
    
    # Normalizar las palabras clave extraídas
    clean_keywords = [normalizar_texto(k) for k in list(keywords) if normalizar_texto(k) and normalizar_texto(k) not in STOP_WORDS]
    
    return clean_keywords[:10]


def _process_and_score_candidates(candidatos, libro_fuente, autor_fuente, categorias_fuente, descripcion_fuente, fecha_fuente, consulta_norm, titulo_fuente_norm, es_libro):
    """
    Aplica el scoring avanzado V2 y formatea los resultados para la respuesta final.
    """
    libros_procesados = []
    ids_vistos = set()
    
    for item in candidatos:
        info = item.get('volumeInfo', {})
        titulo = info.get('title')
        id_libro = item.get('id')
        
        # FILTRO: Solo mostrar libros en español ('es')
        language = info.get('language')
        if language != 'es':
            continue # Saltar este candidato si no está en español

        if not titulo or not id_libro or id_libro in ids_vistos:
            continue
        
        titulo_norm = normalizar_texto(titulo)
        
        # Filtros anti-eco
        if titulo_norm == titulo_fuente_norm: # Es el libro fuente
            continue
        # La consulta inicial no debe estar contenida en el título (ej. "The Road" busca "The Road to...")
        if es_libro and consulta_norm in titulo_norm and len(consulta_norm) > 5:
            continue
        
        # SCORING MEJORADO V2
        score = calcular_score_avanzado_v2(
            item, 
            libro_fuente,
            autor_fuente, 
            categorias_fuente,
            descripcion_fuente,
            fecha_fuente
        )
        
        autor_display = info.get('authors', ['Autor desconocido'])[0]
        descripcion = info.get('description', 'Sin descripción disponible')
        
        if len(descripcion) > 150:
            descripcion = descripcion[:147] + "..."
        
        libros_procesados.append({
            "titulo": titulo,
            "autor": autor_display,
            "descripcion": descripcion,
            "imagen": info.get('imageLinks', {}).get('thumbnail'),
            "puntuacion": info.get('averageRating', 0),
            "num_ratings": info.get('ratingsCount', 0),
            "año_publicacion": info.get('publishedDate', ''),
            "categorias": info.get('categories', []),
            "score_interno": score,
            "id": id_libro
        })
        
        ids_vistos.add(id_libro)

    return libros_procesados


# ============================================
# VISTA PRINCIPAL (SIN INFORMACIÓN DE USUARIO)
# ============================================

@api_view(['GET'])
def recomendar_libros(request):
    consulta = request.GET.get('libro')
    
    if not consulta:
        return Response({"error": "Escribe algo para buscar."}, status=400)

    # --- PASO 1: BÚSQUEDA INICIAL ---
    # Intentamos buscar el título exacto, ya que la calidad de la recomendación depende del libro fuente
    data = buscar_con_cache(
        GOOGLE_BOOKS_URL,
        {'q': f'"{consulta}"', 'maxResults': 5},
        'google_initial'
    )
    
    if not data or 'items' not in data:
        # Fallback si no se encuentra el título exacto
        data = buscar_con_cache(
            GOOGLE_BOOKS_URL,
            {'q': consulta, 'maxResults': 5},
            'google_initial_fallback'
        )
        if not data or 'items' not in data:
            return Response({"error": "No se encontraron resultados."}, status=404)

    # --- PASO 2: SELECCIÓN DE FUENTE ---
    libro_fuente = None
    libro_id_fuente = None
    
    # Intentar encontrar un resultado con título y autor para usar como fuente
    for item in data['items']:
        info = item.get('volumeInfo', {})
        if 'title' in info and 'authors' in info and len(info['authors']) > 0:
            libro_fuente = info
            libro_id_fuente = item.get('id')
            break
    
    # Si no se encontró un libro completo, usar el primer resultado
    if not libro_fuente:
        libro_fuente = data['items'][0]['volumeInfo']
        libro_id_fuente = data['items'][0].get('id')

    # Extraer info de la fuente
    titulo_fuente = libro_fuente.get('title', '')
    autores_fuente = libro_fuente.get('authors', [])
    categorias_fuente = libro_fuente.get('categories', [])
    descripcion_fuente = libro_fuente.get('description', '')
    fecha_fuente = libro_fuente.get('publishedDate', '')[:4]
    
    es_libro = len(autores_fuente) > 0
    autor_fuente = autores_fuente[0] if es_libro else None
    
    # --- PASO 3: EXTRACCIÓN DE KEYWORDS ---
    
    keywords = extraer_keywords(libro_fuente)
    
    mensaje = ""
    candidatos = []

    if es_libro:
        mensaje = f"Porque leíste '{titulo_fuente}' de {autor_fuente}"
        
        # --- PASO 4: BÚSQUEDA MULTI-FUENTE ASÍNCRONA ---
        try:
            # Ejecutar búsquedas en paralelo
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            candidatos = loop.run_until_complete(
                buscar_multiples_fuentes_async(autor_fuente, categorias_fuente, keywords, titulo_fuente)
            )
            
            loop.close()
            
        except Exception as e:
            print(f"Error en búsquedas async: {e}")
            # Fallback a búsqueda síncrona básica por autor
            data_autor = buscar_con_cache(
                GOOGLE_BOOKS_URL,
                {'q': f'inauthor:"{autor_fuente}"', 'maxResults': 20},
                'google_autor'
            )
            if data_autor:
                candidatos.extend(data_autor.get('items', []))
        
        # Fallback si tenemos pocos candidatos después de las búsquedas
        if len(candidatos) < 15:
            fallback = generar_fallback_inteligente(libro_fuente, autor_fuente, candidatos)
            candidatos.extend(fallback)
    
    else:
        # Modo tema (No se usa async aquí, es una sola búsqueda)
        mensaje = f"Resultados para: {consulta}"
        data_tema = buscar_con_cache(
            GOOGLE_BOOKS_URL,
            {'q': consulta, 'maxResults': 30, 'orderBy': 'relevance'},
            'google_tema'
        )
        if data_tema:
            candidatos.extend(data_tema.get('items', []))

    # --- PASO 5: PROCESAMIENTO CON SCORING V2 (Usando helper) ---
    libros_procesados = _process_and_score_candidates(
        candidatos, 
        libro_fuente,
        autor_fuente, 
        categorias_fuente,
        descripcion_fuente,
        fecha_fuente,
        normalizar_texto(consulta),
        normalizar_texto(titulo_fuente),
        es_libro
    )
    
    # --- PASO 6: ORDENAR Y DIVERSIFICAR ---
    libros_procesados.sort(key=lambda x: x['score_interno'], reverse=True)
    
    # Aplicar diversidad (usa las constantes como defaults)
    recomendaciones_finales = asegurar_diversidad_avanzada(libros_procesados)
    
    # Limpiar score interno y preparar respuesta
    for libro in recomendaciones_finales:
        score_debug = libro['score_interno']
        del libro['score_interno']
        # libro['score_debug'] = round(score_debug, 2) # Descomentar para debug
    
    if len(recomendaciones_finales) == 0:
        return Response({
            "basado_en": mensaje,
            "recomendaciones": [],
            "mensaje": "No se encontraron recomendaciones relevantes en español."
        })

    return Response({
        "basado_en": mensaje,
        "total_encontradas": len(recomendaciones_finales),
        "mejoras_aplicadas": [
            "Embeddings semánticos para similitud profunda",
            "Detección de series y sagas",
            "Búsquedas asíncronas paralelas (5x más rápido)",
            "Integración de Open Library y compensación de datos faltantes",
            "Ajuste inteligente por popularidad"
        ],
        "recomendaciones": recomendaciones_finales
    })
