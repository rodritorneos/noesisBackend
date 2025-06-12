from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from database import engine, get_db
from models import Usuario, Favorito, Visita, Puntaje, Base
from schemas import (
    UsuarioRegistro, UsuarioLogin, UsuarioResponse, UsuarioInfo,
    FavoritoRequest, FavoritoResponse, FavoritosUsuarioResponse, FavoritoAddResponse,
    VisitaRequest, VisitaResponse, VisitasUsuarioResponse,
    PuntajeRequest, PuntajeResponse, PuntajeUpdateResponse,
    MessageResponse, RegistroResponse, LoginResponse,
    HealthResponse, RootResponse
)

# Crear las tablas
Base.metadata.create_all(bind=engine)

# Crear la aplicación FastAPI
app = FastAPI(title="API Usuarios, Favoritos, Visitas y Puntajes Noesis", version="2.0.0")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Funciones auxiliares
def get_user_by_email(db: Session, email: str):
    return db.query(Usuario).filter(Usuario.email == email).first()

def create_user(db: Session, email: str, password: str):
    db_user = Usuario(email=email, password=password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Crear puntaje inicial
    db_puntaje = Puntaje(
        usuario_id=db_user.id,
        puntaje_obtenido=0,
        puntaje_total=20,
        nivel="Básico"
    )
    db.add(db_puntaje)
    db.commit()
    
    return db_user

# Endpoints de usuarios
@app.get("/usuarios", response_model=List[UsuarioResponse])
async def get_usuarios(db: Session = Depends(get_db)):
    """Obtener todos los usuarios (solo email y password para compatibilidad)"""
    usuarios = db.query(Usuario).all()
    # Manteniendo compatibilidad con el frontend actual
    return [{"email": user.email, "password": user.password} for user in usuarios]

@app.post("/usuarios/registro", response_model=RegistroResponse)
async def registrar_usuario(usuario: UsuarioRegistro, db: Session = Depends(get_db)):
    """Registrar un nuevo usuario"""
    # Verificar si el email ya existe
    if get_user_by_email(db, usuario.email):
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    # Crear nuevo usuario
    nuevo_usuario = create_user(db, usuario.email, usuario.password)
    
    return {"message": "Usuario registrado exitosamente", "email": usuario.email}

@app.post("/usuarios/login", response_model=LoginResponse)
async def login_usuario(usuario: UsuarioLogin, db: Session = Depends(get_db)):
    """Autenticar usuario"""
    usuario_encontrado = get_user_by_email(db, usuario.email)
    
    if not usuario_encontrado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if usuario_encontrado.password != usuario.password:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    
    return {"message": "Login exitoso", "email": usuario.email}

@app.get("/usuarios/{email}", response_model=UsuarioInfo)
async def obtener_usuario(email: str, db: Session = Depends(get_db)):
    """Obtener información de un usuario específico"""
    usuario = get_user_by_email(db, email)
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return {"email": usuario.email}

@app.delete("/usuarios/{email}", response_model=MessageResponse)
async def eliminar_usuario(email: str, db: Session = Depends(get_db)):
    """Eliminar un usuario y todos sus datos relacionados"""
    usuario = get_user_by_email(db, email)
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # SQLAlchemy eliminará automáticamente los datos relacionados gracias a cascade="all, delete-orphan"
    db.delete(usuario)
    db.commit()
    
    return {"message": "Usuario, favoritos, visitas y puntajes eliminados exitosamente"}

# Endpoints de favoritos
@app.post("/usuarios/{email}/favoritos", response_model=FavoritoAddResponse)
async def agregar_favorito(email: str, favorito: FavoritoRequest, db: Session = Depends(get_db)):
    """Agregar una clase a favoritos"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar si ya está en favoritos
    favorito_existente = db.query(Favorito).filter(
        Favorito.usuario_id == usuario.id,
        Favorito.clase_id == favorito.clase_id
    ).first()
    
    if favorito_existente:
        raise HTTPException(status_code=400, detail="La clase ya está en favoritos")
    
    # Crear nuevo favorito
    nuevo_favorito = Favorito(
        usuario_id=usuario.id,
        clase_id=favorito.clase_id,
        nombre_clase=favorito.nombre_clase,
        imagen_path=favorito.imagen_path
    )
    
    db.add(nuevo_favorito)
    db.commit()
    db.refresh(nuevo_favorito)
    
    return {
        "message": "Favorito agregado exitosamente",
        "favorito": {
            "clase_id": nuevo_favorito.clase_id,
            "nombre_clase": nuevo_favorito.nombre_clase,
            "imagen_path": nuevo_favorito.imagen_path
        }
    }

@app.delete("/usuarios/{email}/favoritos/{clase_id}", response_model=MessageResponse)
async def remover_favorito(email: str, clase_id: str, db: Session = Depends(get_db)):
    """Remover una clase de favoritos"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    favorito = db.query(Favorito).filter(
        Favorito.usuario_id == usuario.id,
        Favorito.clase_id == clase_id
    ).first()
    
    if not favorito:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    
    db.delete(favorito)
    db.commit()
    
    return {"message": "Favorito removido exitosamente"}

@app.get("/usuarios/{email}/favoritos", response_model=FavoritosUsuarioResponse)
async def obtener_favoritos_usuario(email: str, db: Session = Depends(get_db)):
    """Obtener los favoritos de un usuario"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    favoritos = db.query(Favorito).filter(Favorito.usuario_id == usuario.id).all()
    
    favoritos_list = [
        {
            "clase_id": fav.clase_id,
            "nombre_clase": fav.nombre_clase,
            "imagen_path": fav.imagen_path
        }
        for fav in favoritos
    ]
    
    return {
        "email": email,
        "favoritos": favoritos_list,
        "total": len(favoritos_list)
    }

@app.put("/usuarios/{email}/favoritos/{clase_id}", response_model=MessageResponse)
async def actualizar_favorito(email: str, clase_id: str, favorito_actualizado: FavoritoRequest, db: Session = Depends(get_db)):
    """Actualizar información de un favorito"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    favorito = db.query(Favorito).filter(
        Favorito.usuario_id == usuario.id,
        Favorito.clase_id == clase_id
    ).first()
    
    if not favorito:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    
    favorito.clase_id = favorito_actualizado.clase_id
    favorito.nombre_clase = favorito_actualizado.nombre_clase
    favorito.imagen_path = favorito_actualizado.imagen_path
    
    db.commit()
    
    return {"message": "Favorito actualizado exitosamente"}

# Endpoints de visitas
@app.post("/usuarios/{email}/visitas", response_model=MessageResponse)
async def registrar_visita(email: str, visita: VisitaRequest, db: Session = Depends(get_db)):
    """Registrar una visita a una clase"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Buscar si ya existe una visita para esta clase
    visita_existente = db.query(Visita).filter(
        Visita.usuario_id == usuario.id,
        Visita.clase_id == visita.clase_id
    ).first()
    
    if visita_existente:
        # Incrementar contador
        visita_existente.count += 1
        db.commit()
    else:
        # Crear nueva visita
        nueva_visita = Visita(
            usuario_id=usuario.id,
            clase_id=visita.clase_id,
            count=1
        )
        db.add(nueva_visita)
        db.commit()
    
    return {"message": "Visita registrada exitosamente"}

@app.get("/usuarios/{email}/visitas", response_model=VisitasUsuarioResponse)
async def obtener_visitas_usuario(email: str, db: Session = Depends(get_db)):
    """Obtener las visitas de un usuario"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    visitas = db.query(Visita).filter(Visita.usuario_id == usuario.id).all()
    
    visitas_list = [
        {
            "clase_id": visita.clase_id,
            "count": visita.count
        }
        for visita in visitas
    ]
    
    total_visitas = sum(visita.count for visita in visitas)
    
    return {
        "email": email,
        "visitas": visitas_list,
        "total_visitas": total_visitas
    }

# Endpoints de puntajes
@app.get("/usuarios/{email}/puntajes", response_model=PuntajeResponse)
async def obtener_puntajes_usuario(email: str, db: Session = Depends(get_db)):
    """Obtener los puntajes de un usuario"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    puntaje = db.query(Puntaje).filter(Puntaje.usuario_id == usuario.id).first()
    
    if not puntaje:
        # Crear puntaje inicial si no existe
        puntaje = Puntaje(
            usuario_id=usuario.id,
            puntaje_obtenido=0,
            puntaje_total=20,
            nivel="Básico"
        )
        db.add(puntaje)
        db.commit()
        db.refresh(puntaje)
    
    return {
        "email": email,
        "puntaje_obtenido": puntaje.puntaje_obtenido,
        "puntaje_total": puntaje.puntaje_total,
        "nivel": puntaje.nivel
    }

@app.post("/usuarios/{email}/puntajes", response_model=PuntajeUpdateResponse)
async def actualizar_puntajes_usuario(email: str, puntaje_request: PuntajeRequest, db: Session = Depends(get_db)):
    """Actualizar los puntajes de un usuario solo si es mejor que el anterior"""
    usuario = get_user_by_email(db, email)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    puntaje = db.query(Puntaje).filter(Puntaje.usuario_id == usuario.id).first()
    is_new_best = False
    
    if not puntaje:
        # Crear nuevo puntaje
        puntaje = Puntaje(
            usuario_id=usuario.id,
            puntaje_obtenido=puntaje_request.puntaje_obtenido,
            puntaje_total=puntaje_request.puntaje_total,
            nivel=puntaje_request.nivel
        )
        db.add(puntaje)
        is_new_best = True
    else:
        # Comparar porcentajes
        porcentaje_actual = (puntaje.puntaje_obtenido / puntaje.puntaje_total) * 100
        porcentaje_nuevo = (puntaje_request.puntaje_obtenido / puntaje_request.puntaje_total) * 100
        
        if porcentaje_nuevo > porcentaje_actual:
            puntaje.puntaje_obtenido = puntaje_request.puntaje_obtenido
            puntaje.puntaje_total = puntaje_request.puntaje_total
            puntaje.nivel = puntaje_request.nivel
            is_new_best = True
    
    db.commit()
    
    return {
        "message": "Puntaje procesado exitosamente",
        "data": {
            "is_new_best": is_new_best,
            "puntaje_obtenido": puntaje_request.puntaje_obtenido,
            "puntaje_total": puntaje_request.puntaje_total,
            "nivel": puntaje_request.nivel
        }
    }

# Endpoints de información general
@app.get("/", response_model=RootResponse)
async def root():
    """Endpoint raíz de la API"""
    return {
        "message": "API de usuarios, favoritos, visitas y puntajes SQLite",
        "version": "2.0.0",
        "database": "SQLite",
        "endpoints": {
            "usuarios": "/usuarios/{email}",
            "registro": "/usuarios/registro",
            "login": "/usuarios/login",
            "favoritos": "/usuarios/{email}/favoritos",
            "visitas": "/usuarios/{email}/visitas",
            "puntajes": "/usuarios/{email}/puntajes"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Verificar el estado de la API"""
    try:
        usuarios_count = db.query(Usuario).count()
        favoritos_count = db.query(Favorito).count()
        visitas_count = db.query(Visita).count()
        puntajes_count = db.query(Puntaje).count()
        
        return {
            "status": "healthy",
            "database": "SQLite",
            "usuarios_registrados": usuarios_count,
            "total_favoritos": favoritos_count,
            "total_visitas": visitas_count,
            "total_puntajes": puntajes_count,
            "database_ok": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database_ok": False
        }