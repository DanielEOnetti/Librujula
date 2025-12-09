# 📚 LIBRÚJULA: El Netflix Literario

[![Django](https://img.shields.io/badge/Django-5.2.8-092E20.svg?logo=django)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![REST Framework](https://img.shields.io/badge/DRF-FF105A.svg?logo=djangorestframework)](https://www.django-rest-framework.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🌟 Descripción General

**LIBRÚJULA** es un avanzado motor de recomendación de libros que utiliza inteligencia artificial y procesamiento de lenguaje natural (NLP) para sugerir títulos a los usuarios. Su objetivo es replicar la experiencia de descubrimiento rápido y personalizado de una plataforma de *streaming*, pero aplicada al mundo literario.

El proyecto está dividido en un **Backend (Django REST API)** y un **Frontend (React)**.

## ✨ Características Destacadas del Algoritmo

La lógica de recomendación reside en `recomendaciones/views.py` y utiliza un sistema de *Scoring Avanzado* para ofrecer resultados de alta calidad:

* **Scoring Semántico Profundo:** Uso de *embeddings* (a través de la librería `sentence-transformers`) para calcular la similitud real entre las descripciones de los libros, y no solo por coincidencia de palabras clave.
* **Búsqueda Multi-Fuente Asíncrona:** Ejecuta múltiples búsquedas en paralelo a la **API de Google Books** y a **Open Library** usando `aiohttp` y `asyncio`, garantizando velocidad y una gran base de candidatos.
* **Ajuste por Popularidad:** Aplica un factor de corrección al *rating* para dar un ligero *boost* a libros de nicho con buenas reseñas, mitigando el sesgo hacia los *mega-bestsellers*.
* **Detección de Series:** Identifica sagas y ofrece un *bonus* por libros de la misma serie, priorizando el orden de lectura.
* **Filtro de Diversidad:** Garantiza una variedad de autores, épocas y series en los resultados finales, evitando la repetición excesiva de títulos similares.

## ⚙️ Tecnologías

| Componente | Tecnología | Propósito Clave |
| :--- | :--- | :--- |
| **Backend** | Python, Django, DRF | API RESTful y orquestación del algoritmo. |
| **NLP** | `sentence-transformers` | Cálculo de Similitud Semántica (Embeddings). |
| **Asincronía** | `aiohttp`, `asyncio` | Búsquedas paralelas rápidas en APIs externas. |
| **Frontend** | React, Vite | Interfaz de usuario dinámica estilo Netflix. |
| **Intercomunicación** | `corsheaders` | Permite la comunicación entre React (puerto 5173) y Django (puerto 8000). |

## 🚀 Instalación y Ejecución Local

Asegúrate de tener **Python 3.10+** y **Node.js/npm** instalados.

### 1. Preparación y Clonación

```bash
# 1. Clonar el repositorio
git clone [https://github.com/DanielEOnetti/Librujula.git](https://github.com/DanielEOnetti/Librujula.git)
cd Librujula
2. Configuración del Backend (Django/Python)
Crear y activar el entorno virtual:

Bash

python -m venv venv
source venv/bin/activate  # macOS/Linux
# .\venv\Scripts\activate  # Windows Powershell
Instalar dependencias de Python: La librería sentence-transformers es esencial para el scoring.

Bash

pip install -r requirements.txt
(Asegúrate de haber creado el archivo requirements.txt con la lista de dependencias)

Ejecutar migraciones y servidor:

Bash

python manage.py makemigrations
python manage.py migrate
python manage.py runserver
# La API estará en: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
3. Configuración del Frontend (React/Vite)
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
# La aplicación estará en: http://localhost:5173/
⚠️ Nota sobre Embeddings
El algoritmo de recomendación utiliza la función obtener_modelo_embeddings() que carga perezosamente el modelo multilingual 'paraphrase-multilingual-MiniLM-L12-v2' de Hugging Face. La primera vez que ejecutes una recomendación, la carga del modelo puede tomar varios segundos, ya que se descarga a tu caché local.
