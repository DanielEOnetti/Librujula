
LIBRÚJULA: El Netflix Literario
📖 Descripción del Proyecto
LIBRÚJULA es un avanzado motor de recomendación de libros desarrollado con Django (backend API) y React (frontend). El objetivo es ofrecer una experiencia de descubrimiento de libros similar a las plataformas de streaming (de ahí el subtítulo "El Netflix Literario"), utilizando un potente algoritmo que combina datos de múltiples fuentes con análisis de similitud semántica.

El backend gestiona búsquedas en tiempo real en la API de Google Books y Open Library, aplicando un sistema de scoring avanzado para clasificar y diversificar las recomendaciones.

✨ Características Principales
El proyecto se destaca por su complejidad algorítmica y su arquitectura moderna:

Backend (Algoritmo de Recomendación)
Búsqueda Multi-Fuente Asíncrona: Utiliza aiohttp y asyncio para realizar múltiples búsquedas en paralelo a Google Books y Open Library, minimizando los tiempos de espera y maximizando la cantidad de candidatos.

Similitud Semántica Avanzada: Emplea Embeddings (a través de sentence-transformers) para calcular la similitud profunda entre las descripciones de los libros, ofreciendo recomendaciones más precisas que la simple coincidencia de palabras clave.

Scoring Inteligente (V2): El puntaje final (score_interno) se calcula en base a:

Coincidencia de Autor y Categoría.

Detección de series/sagas con bonus específico.

Puntuación de Rating ajustada por popularidad (ajuste anti-bestseller).

Puntaje de Similitud Semántica (Embeddings).

Aseguramiento de la Diversidad: Implementa un filtro para evitar la sobresaturación, limitando el número de recomendaciones por Autor, Década de Publicación y Serie/Saga.

Caching Eficiente: Utiliza django.core.cache para almacenar resultados de API externas con TTLs variables, mejorando la velocidad y reduciendo la carga de las APIs externas.

Frontend (Interfaz de Usuario)
Diseño Dinámico: La interfaz cambia entre un modo-landing (buscador centrado) y un modo-app (buscador superior con cuadrícula de resultados), inspirado en el diseño de Netflix.

Cuadrícula Interactiva (Grid): Muestra las recomendaciones con un efecto visual de zoom al pasar el ratón (:hover), replicando la experiencia de exploración.

Llamada a API: El frontend realiza la llamada a http://127.0.0.1:8000/api/recomendar/ con la consulta del usuario.

🛠️ Tecnologías Utilizadas
Backend (API)
Framework: Django 5.2.8

API: Django REST Framework

Comunicaciones: aiohttp, requests

Algoritmo: numpy, sentence-transformers (para embeddings)

Configuración: corsheaders (permitiendo la comunicación con http://localhost:5173)

Frontend (Cliente)
Librería: React

Build Tool: Vite

Lenguaje: JavaScript (ES6+), JSX

Estilos: CSS (con fuentes de Google Fonts: Bebas Neue, Roboto)

🏗️ Estructura del Proyecto
El código está organizado en una arquitectura de monorepo separando el backend de Django del frontend de React (asumiendo que src es la carpeta raíz de la aplicación React).

.
├── core/                       # Configuración principal de Django
│   ├── settings.py             # Configuración de apps, middleware, CORS (5173)
│   ├── urls.py                 # Enrutamiento principal: path('api/', include('recomendaciones.urls'))
├── recomendaciones/          # Aplicación principal de Django para la lógica
│   ├── urls.py                 # Enrutamiento de la API: path('recomendar/', views.recomendar_libros)
│   └── views.py                # 🔑 Lógica del algoritmo de recomendación
└── src/                        # Aplicación de Frontend (React/Vite)
    ├── App.jsx                 # Lógica de la interfaz de usuario, manejo de estados, llamada a fetch
    ├── App.css                 # Estilos específicos de la aplicación (Modo landing/app, tarjetas)
    └── index.css               # Estilos globales (fuentes, colores base)
🎯 Endpoint de la API
La funcionalidad principal se expone a través de un único endpoint:

Método	URL	Descripción
GET	/api/recomendar/	Obtiene recomendaciones de libros basadas en una consulta.
Ejemplo de Uso:

GET http://127.0.0.1:8000/api/recomendar/?libro=Cien%20años%20de%20soledad
🚀 Instalación y Ejecución
1. Backend (Django)
Clonar el repositorio:

Bash
# Asume que este es el comando de clonación
git clone [URL_DEL_REPOSITORIO]
cd [URL_DEL_REPOSITORIO]
Crear un entorno virtual y activar:

Bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# .\venv\Scripts\activate  # Windows
Instalar dependencias de Python: El archivo recomendaciones/views.py sugiere las siguientes librerías clave. Debes instalarlas:

Bash
pip install django djangorestframework django-cors-headers requests numpy aiohttp

# ⚠️ Importante para el cálculo de Embeddings Semánticos:
pip install sentence-transformers
Ejecutar migraciones y servidor:

Bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
# El servidor estará activo en http://127.0.0.1:8000/
2. Frontend (React)
Navegar a la carpeta del frontend:

Bash
cd src
Instalar dependencias de Node.js:

Bash
npm install
# o yarn install
Ejecutar el servidor de desarrollo:

Bash
npm run dev
# o yarn dev
# El frontend estará activo en http://localhost:5173/
Asegúrate de que ambos servidores (Django en 8000 y Vite en 5173) estén corriendo simultáneamente para que la aplicación funcione correctamente.