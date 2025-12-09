import { useState } from 'react'
import './App.css'

function App() {
  const [libroInput, setLibroInput] = useState('')
  const [recomendaciones, setRecomendaciones] = useState([])
  const [cargando, setCargando] = useState(false)
  const [mensaje, setMensaje] = useState('')
  
  // Nuevo estado para controlar si estamos en "Intro" o en "Resultados"
  const [busquedaIniciada, setBusquedaIniciada] = useState(false)

  const manejarBusqueda = async () => {
    if (!libroInput.trim()) return;

    // Activamos el modo "Resultados" inmediatamente
    setBusquedaIniciada(true);
    setCargando(true);
    setMensaje('');
    setRecomendaciones([]);

    try {
      const respuesta = await fetch(`http://127.0.0.1:8000/api/recomendar/?libro=${encodeURIComponent(libroInput)}`);
      const datos = await respuesta.json();

      if (datos.error) {
        setMensaje(datos.error);
      } else {
        setRecomendaciones(datos.recomendaciones);
        setMensaje(datos.basado_en ? `Porque leíste: "${datos.basado_en}"` : `Resultados para: "${libroInput}"`);
      }
    } catch (error) {
      setMensaje("Error de conexión con el servidor.");
    } finally {
      setCargando(false);
    }
  }

  // Función para resetear y volver al inicio (opcional, al hacer click en el logo si quisieras)
  const resetear = () => {
    setBusquedaIniciada(false);
    setLibroInput('');
    setRecomendaciones([]);
  }

  return (
    // La clase cambia dinámicamente: 'modo-landing' (centro) o 'modo-app' (arriba)
    <div className={`contenedor-principal ${busquedaIniciada ? 'modo-app' : 'modo-landing'}`}>
      
      {/* SECCIÓN SUPERIOR (Header / Intro) */}
      <div className="seccion-input">
        
        {/* El título solo se muestra si NO se ha iniciado la búsqueda */}
        {!busquedaIniciada && (
          <div className="bloque-titulo">
            <h1>LIBRÚJULA</h1>
            <p className="subtitulo">El Netflix Literario</p>
          </div>
        )}
        
        <div className="buscador">
          <input 
            type="text" 
            placeholder="Títulos, autores, géneros..."
            value={libroInput}
            onChange={(e) => setLibroInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && manejarBusqueda()}
            disabled={cargando}
            autoFocus
          />
          <button onClick={manejarBusqueda} disabled={cargando || !libroInput.trim()}>
            {cargando ? '...' : 'BUSCAR'}
          </button>
        </div>

        {mensaje && <div className="mensaje-estado">{mensaje}</div>}
      </div>

      {/* SECCIÓN RESULTADOS (Solo visible cuando hay búsqueda iniciada) */}
      {busquedaIniciada && (
        <div className="area-resultados">
           {/* Botón flotante para volver (opcional) o mensaje empty */}
          {!cargando && recomendaciones.length === 0 && !mensaje && (
             <div className="empty-state">No se encontraron resultados.</div>
          )}

          <div className="grid-libros">
            {recomendaciones.map((libro, index) => (
              <TarjetaLibro key={index} libro={libro} index={index} />
            ))}
            
            {cargando && [...Array(10)].map((_, i) => (
                <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

    </div>
  )
}

// --- Componentes auxiliares iguales que antes ---

function TarjetaLibro({ libro, index }) {
  const [imagenError, setImagenError] = useState(false);
  const porcentaje = libro.puntuacion ? Math.round((libro.puntuacion / 5) * 100) : 85;

  return (
    <div className="tarjeta-libro" style={{ animationDelay: `${index * 0.05}s` }}>
      <div className="contenedor-portada">
        {libro.imagen && !imagenError ? (
           <img src={libro.imagen} alt={libro.titulo} className="portada-libro" onError={() => setImagenError(true)} loading="lazy" />
        ) : (
          <div className="sin-portada"><span>{libro.titulo}</span></div>
        )}
      </div>
      <div className="info-libro">
        <h3>{libro.titulo}</h3>
        <h4>{libro.autor}</h4>
        <div className="stats-libro">
          <span className="match-score">{porcentaje}% Match</span>
        </div>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="tarjeta-libro" style={{ pointerEvents: 'none', background: 'transparent' }}>
      <div className="contenedor-portada skeleton"></div>
    </div>
  )
}

export default App