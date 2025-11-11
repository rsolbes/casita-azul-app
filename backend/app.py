import os
import uuid
from datetime import datetime
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# CORS Configuration
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "https://app-externos.netlify.app,https://casita-azul-admin.netlify.app,http://localhost:4200,http://localhost:50687"
)
origins_list = [origin.strip() for origin in CORS_ORIGINS.split(',')]
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": origins_list,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
            "max_age": 3600
        }
    }
)

print(f"✅ Orígenes CORS permitidos: {origins_list}")

# --- GLOBALS - Initialize on startup ---
_supabase_client = None
_supabase_admin_client = None
_db_pool = None

# --- INITIALIZE CONNECTIONS ON STARTUP ---
def init_connections():
    """Initialize all connections at startup instead of lazy loading"""
    global _supabase_client, _supabase_admin_client, _db_pool
    
    print("🔄 Inicializando conexiones...")
    
    # Initialize Supabase client
    try:
        SUPABASE_URL = os.getenv("SUPABASE_URL", "https://izozjytmktbuhpttczid.supabase.co")
        SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
        if SUPABASE_ANON_KEY:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            print("✅ Supabase client inicializado")
    except Exception as e:
        print(f"⚠️  Error inicializando Supabase client: {e}")
    
    # Initialize Supabase admin client
    try:
        SUPABASE_URL = os.getenv("SUPABASE_URL", "https://izozjytmktbuhpttczid.supabase.co")
        SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
        if SUPABASE_SERVICE_KEY:
            _supabase_admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print("✅ Admin client configurado")
    except Exception as e:
        print(f"⚠️  Error inicializando Admin client: {e}")
    
    # Initialize database pool
    try:
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("PASSWORD")
        db_host = os.getenv("HOST")
        db_port = os.getenv("DB_PORT", "6543")  # Cambiado de PORT a DB_PORT
        db_name = os.getenv("DBNAME")
        
        print(f"🔍 Intentando conectar a PostgreSQL:")
        print(f"   Host: {db_host}")
        print(f"   Port: {db_port}")
        print(f"   User: {db_user}")
        print(f"   Database: {db_name}")
        print(f"   Password: {'[CONFIGURED]' if db_password else '[MISSING]'}")
        
        if not all([db_user, db_password, db_host, db_name]):
            raise ValueError(f"Faltan variables de entorno requeridas: DB_USER={bool(db_user)}, PASSWORD={bool(db_password)}, HOST={bool(db_host)}, DBNAME={bool(db_name)}")
        
        _db_pool = pool.ThreadedConnectionPool(
            1,  # min connections
            5,  # max connections
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            dbname=db_name,
            sslmode='require',
            connect_timeout=30  # 30 second timeout (increased from 10)
        )
        print("✅ Database pool creado (1-5 conexiones)")
        
        # Test the connection
        print("🔍 Probando conexión...")
        test_conn = _db_pool.getconn()
        cursor = test_conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        cursor.close()
        _db_pool.putconn(test_conn)
        print(f"✅ Conexión a base de datos verificada (resultado: {result})")
        
    except Exception as e:
        print(f"❌ ERROR CRÍTICO creando pool de base de datos:")
        print(f"❌ Tipo de error: {type(e).__name__}")
        print(f"❌ Mensaje: {str(e)}")
        print(f"❌ DB_USER: {os.getenv('DB_USER', '[NOT SET]')}")
        print(f"❌ HOST: {os.getenv('HOST', '[NOT SET]')}")
        print(f"❌ DB_PORT: {os.getenv('DB_PORT', '[NOT SET - using default 6543]')}")
        print(f"❌ DBNAME: {os.getenv('DBNAME', '[NOT SET]')}")
        print(f"❌ PASSWORD: {'[CONFIGURED]' if os.getenv('PASSWORD') else '[NOT SET]'}")
        import traceback
        traceback.print_exc()
        _db_pool = None

# Initialize connections when app starts
init_connections()

def get_supabase_client():
    """Get Supabase client"""
    if _supabase_client is None:
        raise ValueError("Supabase client not initialized")
    return _supabase_client

def get_supabase_admin():
    """Get Supabase admin client"""
    if _supabase_admin_client is None:
        raise ValueError("Supabase admin client not initialized")
    return _supabase_admin_client

def get_db_connection():
    """Get a connection from the pool"""
    if _db_pool is None:
        raise ValueError("Database pool not initialized")
    
    try:
        conn = _db_pool.getconn()
        return conn
    except Exception as e:
        print(f"Error obteniendo conexión del pool: {e}")
        raise

def return_db_connection(conn):
    """Return connection to the pool"""
    try:
        if _db_pool and conn:
            _db_pool.putconn(conn)
    except Exception as e:
        print(f"Error retornando conexión al pool: {e}")
        if conn:
            try:
                conn.close()
            except:
                pass

# Storage Configuration
BUCKET_NAME = "imagenes casas"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Helper Functions ---
def get_user_id_from_token(request):
    """Extrae el user ID del token de autorización."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise Exception("No token provided")
    token = auth_header.split(' ')[1]
    user_response = get_supabase_client().auth.get_user(token)
    if not user_response or not user_response.user:
        raise Exception("Invalid token")
    return user_response.user.id

def is_admin(user_id: str) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT role FROM public.profiles WHERE id = %s", (user_id,))
        profile = cursor.fetchone()
        cursor.close()
        if profile and profile['role'] == 'admin':
            return True
        return False
    except Exception as e:
        print(f"Error checking admin role: {e}")
        return False
    finally:
        if conn:
            return_db_connection(conn)

# --- Health Check Endpoints ---
@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        "status": "ok",
        "service": "Casita Azul API",
        "version": "1.0",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Endpoint para verificar que el servidor está funcionando (sin DB)"""
    if request.method == 'OPTIONS':
        return '', 204
    
    return jsonify({
        "status": "ok",
        "message": "Backend is running",
        "cors_origins": origins_list,
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def api_health_check():
    """Health check con verificación de base de datos"""
    if request.method == 'OPTIONS':
        return '', 204
    
    db_status = "not_initialized"
    db_error = None
    
    if _db_pool is None:
        db_status = "pool_not_initialized"
        db_error = "Database pool was not created during startup. Check logs for initialization errors."
    else:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            db_status = "connected"
        except Exception as e:
            db_status = f"error"
            db_error = str(e)
        finally:
            if conn:
                return_db_connection(conn)
    
    response = {
        "status": "ok",
        "database": db_status,
        "supabase_url": os.getenv("SUPABASE_URL", "https://izozjytmktbuhpttczid.supabase.co"),
        "cors_origins": origins_list,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if db_error:
        response["database_error"] = db_error
    
    return jsonify(response), 200

@app.route('/api/debug/config', methods=['GET'])
def debug_config():
    """Endpoint de diagnóstico para verificar configuración (SOLO PARA DEBUG)"""
    return jsonify({
        "environment_variables": {
            "DB_USER": "✅ Configured" if os.getenv("DB_USER") else "❌ Missing",
            "PASSWORD": "✅ Configured" if os.getenv("PASSWORD") else "❌ Missing",
            "HOST": os.getenv("HOST", "❌ Missing"),
            "DB_PORT": os.getenv("DB_PORT", "❌ Missing (using default: 6543)"),
            "DBNAME": os.getenv("DBNAME", "❌ Missing"),
            "SUPABASE_URL": "✅ Configured" if os.getenv("SUPABASE_URL") else "❌ Missing",
            "SUPABASE_ANON_KEY": "✅ Configured" if os.getenv("SUPABASE_ANON_KEY") else "❌ Missing",
            "SUPABASE_SERVICE_KEY": "✅ Configured" if os.getenv("SUPABASE_SERVICE_KEY") else "❌ Missing",
            "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "❌ Missing"),
        },
        "database_pool_status": "initialized" if _db_pool else "not_initialized",
        "supabase_client_status": "initialized" if _supabase_client else "not_initialized",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

# --- Authentication Endpoints ---
@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'user')

        response = get_supabase_client().auth.sign_up({
            "email": email,
            "password": password
        })

        if response.user:
            new_user_id = response.user.id
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO public.profiles (id, role) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET role = EXCLUDED.role",
                    (new_user_id, role)
                )
                conn.commit()
                cursor.close()
            except Exception as db_error:
                print(f"Error setting profile role during registration for {new_user_id}: {db_error}")
            finally:
                if conn:
                    return_db_connection(conn)

        return jsonify({
            "status": "success",
            "message": "Usuario registrado. Revisa tu email para confirmar."
        }), 201

    except Exception as e:
        print(f"Error en registro: {e}")
        if "already registered" in str(e):
            return jsonify({"error": "Email already registered"}), 409
        return jsonify({"error": str(e)}), 400

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        response = get_supabase_client().auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        return jsonify({
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email
            }
        }), 200

    except Exception as e:
        print(f"Error en login: {e}")
        return jsonify({"error": "Credenciales inválidas"}), 401

@app.route('/api/logout', methods=['POST', 'OPTIONS'])
def logout():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        auth_header = request.headers.get('Authorization')
        token = None
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if token:
            get_supabase_client().auth.sign_out(token)
        else:
            get_supabase_client().auth.sign_out()

        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error en logout: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/api/user', methods=['GET', 'OPTIONS'])
def get_user():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "No token provided"}), 401

        token = auth_header.split(' ')[1]
        user_response = get_supabase_client().auth.get_user(token)
        user = user_response.user

        role = 'user'
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT role FROM public.profiles WHERE id = %s", (user.id,))
            profile = cursor.fetchone()
            cursor.close()
            if profile:
                role = profile['role']
        except Exception as db_error:
            print(f"Error fetching role for user {user.id}: {db_error}")
        finally:
            if conn:
                return_db_connection(conn)

        return jsonify({
            "id": user.id,
            "email": user.email,
            "role": role
        }), 200

    except Exception as e:
        print(f"Error obteniendo usuario: {e}")
        return jsonify({"error": "Token inválido"}), 401

@app.route('/api/refresh', methods=['POST', 'OPTIONS'])
def refresh():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        if not refresh_token:
            return jsonify({"error": "Refresh token required"}), 400

        response = get_supabase_client().auth.refresh_session(refresh_token)

        if not response.session:
            error_message = "Invalid refresh token or session expired"
            return jsonify({"error": error_message}), 401

        return jsonify({
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }), 200

    except Exception as e:
        print(f"Error en refresh: {e}")
        return jsonify({"error": "Failed to refresh token: " + str(e)}), 401

# --- Catalogos Endpoint ---
@app.route('/api/catalogos', methods=['GET', 'OPTIONS'])
def get_catalogos():
    if request.method == 'OPTIONS':
        return '', 204
    
    catalogos = {}
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        tablas_catalogo = [
            'agentes', 'agentes_externos', 'ciudades', 'estados', 
            'estados_fisicos', 'estados_publicacion', 'frecuencias_alquiler',
            'monedas', 'tipos_negocio', 'tipos_propiedad', 'zonas'
        ]
        
        for tabla in tablas_catalogo:
            if tabla == 'ciudades':
                cursor.execute("SELECT id, nombre, estado_id FROM public.ciudades ORDER BY nombre ASC;")
            elif tabla == 'agentes':
                continue
            else:
                cursor.execute(f"SELECT id, nombre FROM public.{tabla} ORDER BY nombre ASC;")
            
            catalogos[tabla] = cursor.fetchall()
            
        cursor.execute("SELECT id, nombre, email, telefono FROM public.agentes ORDER BY nombre ASC;")
        catalogos['agentes'] = cursor.fetchall()

        cursor.close()
        return jsonify(catalogos)
        
    except Exception as e:
        print(f"Error en get_catalogos: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

# --- Properties Endpoints ---
@app.route('/api/propiedades', methods=['GET', 'OPTIONS'])
def get_properties():
    if request.method == 'OPTIONS':
        return '', 204
    
    conn = None
    try:
        tipo_negocio_id = request.args.get('tipo_negocio_id')
        estado_publicacion_id_not_in_str = request.args.get('estado_publicacion_id__not_in')

        query = """
            SELECT p.*,
                   json_agg(
                       json_build_object(
                           'id', pi.id,
                           'url', pi.url,
                           'nombre_archivo', pi.nombre_archivo,
                           'es_principal', pi.es_principal,
                           'orden', pi.orden
                       ) ORDER BY pi.orden ASC
                   ) FILTER (WHERE pi.id IS NOT NULL) as imagenes
            FROM propiedades p
            LEFT JOIN propiedades_imagenes pi ON p.id = pi.propiedad_id
        """

        filters = ["p.deleted_at IS NULL"]
        params = []

        if tipo_negocio_id:
            filters.append("p.tipo_negocio_id = %s")
            params.append(tipo_negocio_id)

        if estado_publicacion_id_not_in_str:
            try:
                excluded_ids = tuple(int(id) for id in estado_publicacion_id_not_in_str.split(','))
                if excluded_ids:
                    filters.append("p.estado_publicacion_id NOT IN %s")
                    params.append(excluded_ids)
            except ValueError:
                print(f"Filtro 'estado_publicacion_id__not_in' inválido: {estado_publicacion_id_not_in_str}")

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += """
            GROUP BY p.id
            ORDER BY p.id DESC;
        """

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, tuple(params))
        propiedades = cursor.fetchall()
        cursor.close()
        return jsonify({"properties": propiedades})
    except Exception as e:
        print(f"Error en get_properties: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/propiedades/<int:id>', methods=['GET', 'OPTIONS'])
def get_property(id):
    if request.method == 'OPTIONS':
        return '', 204
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT p.*,
                   json_agg(
                       json_build_object(
                           'id', pi.id,
                           'url', pi.url,
                           'nombre_archivo', pi.nombre_archivo,
                           'es_principal', pi.es_principal,
                           'orden', pi.orden
                       ) ORDER BY pi.orden ASC
                   ) FILTER (WHERE pi.id IS NOT NULL) as imagenes
            FROM propiedades p
            LEFT JOIN propiedades_imagenes pi ON p.id = pi.propiedad_id
            WHERE p.id = %s AND p.deleted_at IS NULL
            GROUP BY p.id;
        """
        cursor.execute(query, (id,))
        propiedad = cursor.fetchone()
        cursor.close()

        if propiedad:
            return jsonify(propiedad)
        else:
            return jsonify({"error": "Propiedad no encontrada"}), 404
    except Exception as e:
        print(f"Error en get_property: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/propiedades', methods=['POST'])
def add_property():
    data = request.json
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO propiedades (
                titulo, descripcion, precio, precio_alquiler, valor_administracion,
                habitaciones, alcobas, banos, banos_medios, estacionamientos,
                anio_construccion, piso, m2_terreno, m2_construccion, m2_privada,
                direccion, codigo_postal, lat, lng, registro_publico,
                convenio_url, convenio_validado,
                tipo_negocio_id, tipo_propiedad_id, estado_publicacion_id,
                captado_por_agente_id, moneda_id, frecuencia_alquiler_id,
                estado_fisico_id, estado_id, ciudad_id, zona_id, agente_id,
                agente_externo_id, validado_por_usuario_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            ) RETURNING id;
        """

        cursor.execute(query, (
            data.get('titulo'), data.get('descripcion'), data.get('precio'), data.get('precio_alquiler'), data.get('valor_administracion'),
            data.get('habitaciones', 0), data.get('alcobas', 0), data.get('banos', 0), data.get('banos_medios', 0), data.get('estacionamientos', 0),
            data.get('anio_construccion'), data.get('piso'), data.get('m2_terreno', 0), data.get('m2_construccion', 0), data.get('m2_privada', 0),
            data.get('direccion'), data.get('codigo_postal'), data.get('lat'), data.get('lng'), data.get('registro_publico'),
            data.get('convenio_url'), data.get('convenio_validado', False),
            data.get('tipo_negocio_id'), data.get('tipo_propiedad_id'), data.get('estado_publicacion_id'),
            data.get('captado_por_agente_id'), data.get('moneda_id'), data.get('frecuencia_alquiler_id'),
            data.get('estado_fisico_id'), data.get('estado_id'), data.get('ciudad_id'), data.get('zona_id'), data.get('agente_id'),
            data.get('agente_externo_id'), data.get('validado_por_usuario_id')
        ))

        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return jsonify({"status": "success", "id": new_id}), 201

    except Exception as e:
        print(f"Error en add_property: {e}")
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/propiedades/<int:id>', methods=['PUT'])
def update_property(id):
    data = request.json
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            UPDATE propiedades SET
                titulo = %s, descripcion = %s, precio = %s, precio_alquiler = %s,
                valor_administracion = %s, habitaciones = %s, alcobas = %s, banos = %s,
                banos_medios = %s, estacionamientos = %s, anio_construccion = %s, piso = %s,
                m2_terreno = %s, m2_construccion = %s, m2_privada = %s, direccion = %s,
                codigo_postal = %s, lat = %s, lng = %s, registro_publico = %s,
                convenio_url = %s, convenio_validado = %s,
                tipo_negocio_id = %s, tipo_propiedad_id = %s, estado_publicacion_id = %s,
                captado_por_agente_id = %s, moneda_id = %s, frecuencia_alquiler_id = %s,
                estado_fisico_id = %s, estado_id = %s, ciudad_id = %s, zona_id = %s,
                agente_id = %s, agente_externo_id = %s, validado_por_usuario_id = %s,
                updated_at = NOW()
            WHERE id = %s;
        """

        cursor.execute(query, (
            data.get('titulo'), data.get('descripcion'), data.get('precio'), data.get('precio_alquiler'),
            data.get('valor_administracion'), data.get('habitaciones'), data.get('alcobas'), data.get('banos'),
            data.get('banos_medios'), data.get('estacionamientos'), data.get('anio_construccion'), data.get('piso'),
            data.get('m2_terreno'), data.get('m2_construccion'), data.get('m2_privada'), data.get('direccion'),
            data.get('codigo_postal'), data.get('lat'), data.get('lng'), data.get('registro_publico'),
            data.get('convenio_url'), data.get('convenio_validado'),
            data.get('tipo_negocio_id'), data.get('tipo_propiedad_id'), data.get('estado_publicacion_id'),
            data.get('captado_por_agente_id'), data.get('moneda_id'), data.get('frecuencia_alquiler_id'),
            data.get('estado_fisico_id'), data.get('estado_id'), data.get('ciudad_id'), data.get('zona_id'),
            data.get('agente_id'), data.get('agente_externo_id'), data.get('validado_por_usuario_id'),
            id
        ))
        updated_rows = cursor.rowcount
        conn.commit()
        cursor.close()
        if updated_rows == 0:
            return jsonify({"error": "Propiedad no encontrada"}), 404
        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Error en update_property: {e}")
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/propiedades/<int:id>', methods=['DELETE'])
def delete_property(id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE propiedades SET deleted_at = NOW() WHERE id = %s;", (id,))
        deleted_rows = cursor.rowcount
        conn.commit()
        cursor.close()
        if deleted_rows == 0:
             return jsonify({"error": "Propiedad no encontrada"}), 404
        return jsonify({"status": "deleted (soft)"})
    except Exception as e:
        print(f"Error en delete_property: {e}")
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

# --- Endpoints de Imágenes ---
@app.route('/api/propiedades/<int:propiedad_id>/imagenes', methods=['POST'])
def upload_image(propiedad_id):
    """Subir una imagen a Supabase Storage y guardar referencia en BD"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    es_principal = request.form.get('es_principal', 'false').lower() == 'true'

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    conn = None
    try:
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{propiedad_id}_{uuid.uuid4().hex}.{file_extension}"
        file_path = f"propiedades/{unique_filename}"

        file_content = file.read()

        get_supabase_client().storage.from_(BUCKET_NAME).upload(
            file_path,
            file_content,
            file_options={"content-type": file.content_type}
        )

        public_url = get_supabase_client().storage.from_(BUCKET_NAME).get_public_url(file_path)

        conn = get_db_connection()
        cursor = conn.cursor()

        if es_principal:
            cursor.execute(
                "UPDATE propiedades_imagenes SET es_principal = FALSE WHERE propiedad_id = %s;",
                (propiedad_id,)
            )

        cursor.execute(
            "SELECT COALESCE(MAX(orden), -1) + 1 FROM propiedades_imagenes WHERE propiedad_id = %s;",
            (propiedad_id,)
        )
        orden = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO propiedades_imagenes (propiedad_id, url, nombre_archivo, es_principal, orden)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (propiedad_id, public_url, unique_filename, es_principal, orden)
        )

        image_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()

        return jsonify({
            "status": "success",
            "id": image_id,
            "url": public_url,
            "nombre_archivo": unique_filename,
            "es_principal": es_principal,
            "orden": orden
        }), 201

    except Exception as e:
        print(f"Error en upload_image: {e}")
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/propiedades/<int:propiedad_id>/imagenes/<int:imagen_id>', methods=['DELETE'])
def delete_image(propiedad_id, imagen_id):
    """Eliminar imagen de Supabase Storage y BD"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT nombre_archivo FROM propiedades_imagenes WHERE id = %s AND propiedad_id = %s;",
            (imagen_id, propiedad_id)
        )
        imagen = cursor.fetchone()

        if not imagen:
            cursor.close()
            return jsonify({"error": "Imagen no encontrada"}), 404

        file_path = f"propiedades/{imagen['nombre_archivo']}"
        try:
            get_supabase_client().storage.from_(BUCKET_NAME).remove([file_path])
        except Exception as storage_e:
            print(f"Error deleting from storage (continuing): {storage_e}")

        cursor.execute(
            "DELETE FROM propiedades_imagenes WHERE id = %s;",
            (imagen_id,)
        )
        deleted_rows = cursor.rowcount
        conn.commit()
        cursor.close()

        if deleted_rows == 0:
             return jsonify({"error": "Imagen no encontrada en DB"}), 404

        return jsonify({"status": "deleted"})

    except Exception as e:
        print(f"Error en delete_image: {e}")
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/propiedades/<int:propiedad_id>/imagenes/<int:imagen_id>/principal', methods=['PUT'])
def set_principal_image(propiedad_id, imagen_id):
    """Marcar una imagen como principal"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE propiedades_imagenes SET es_principal = FALSE WHERE propiedad_id = %s;",
            (propiedad_id,)
        )

        cursor.execute(
            "UPDATE propiedades_imagenes SET es_principal = TRUE WHERE id = %s AND propiedad_id = %s;",
            (imagen_id, propiedad_id)
        )
        updated_rows = cursor.rowcount

        conn.commit()
        cursor.close()
        if updated_rows == 0:
            return jsonify({"error": "Imagen no encontrada para esta propiedad"}), 404
        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Error en set_principal_image: {e}")
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)


# --- User Management Endpoints (Admin Only) ---

@app.route('/api/admin/users', methods=['GET'])
def admin_list_users():
    try:
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    u.id, 
                    u.email, 
                    u.created_at,
                    COALESCE(p.role, 'user') as role 
                FROM auth.users u
                LEFT JOIN public.profiles p ON u.id = p.id
                ORDER BY u.created_at DESC;
            """
            cursor.execute(query)
            users_list = cursor.fetchall()
            cursor.close()
            
            for user in users_list:
                 if 'id' in user and hasattr(user['id'], 'hex'):
                     user['id'] = str(user['id'])
                 if 'created_at' in user and hasattr(user['created_at'], 'isoformat'):
                     user['created_at'] = user['created_at'].isoformat()

            return jsonify(users_list), 200
        
        except Exception as db_e:
            print(f"Error listing users from DB: {db_e}")
            if conn: conn.rollback()
            return jsonify({"error": f"Database error: {str(db_e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        print(f"Error listing users: {e}")
        if "Invalid token" in str(e) or "No token provided" in str(e):
            return jsonify({"error": str(e)}), 401
        if "Admin privileges required" in str(e):
             return jsonify({"error": str(e)}), 403
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/api/admin/users', methods=['POST'])
def admin_create_user():
    try:
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403

        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'user')

        if not email or not password:
             return jsonify({"error": "Email and password required"}), 400

        response = get_supabase_admin().auth.admin.create_user({
             "email": email,
             "password": password,
             "email_confirm": True
        })
        new_user = response.user

        conn = None
        profile_set = False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO public.profiles (id, role) VALUES (%s, %s)",
                (new_user.id, role)
            )
            conn.commit()
            cursor.close()
            profile_set = True
        except Exception as db_error:
             print(f"Error inserting profile for new user {new_user.id}. Attempting to delete auth user. Error: {db_error}")
             try:
                 get_supabase_admin().auth.admin.delete_user(new_user.id)
                 print(f"Successfully deleted auth user {new_user.id} after profile insert failure.")
             except Exception as delete_error:
                 print(f"CRITICAL: Failed to delete auth user {new_user.id} after profile insert failure. Manual cleanup needed. Error: {delete_error}")
             return jsonify({"error": f"Failed to set user role in profile: {db_error}"}), 500
        finally:
            if conn:
                return_db_connection(conn)

        return jsonify(new_user.model_dump()), 201
    except Exception as e:
        print(f"Error creating user: {e}")
        if "User already registered" in str(e):
            return jsonify({"error": "User with this email already exists"}), 409
        if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
        if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
        return jsonify({"error": f"Failed to create user: {str(e)}"}), 400

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    try:
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403

        if str(requesting_user_id) == str(user_id):
             return jsonify({"error": "Cannot delete your own admin account"}), 400

        get_supabase_admin().auth.admin.delete_user(user_id)

        return jsonify({"status": "success", "message": f"User {user_id} deleted"}), 200
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
        if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
        if "User not found" in str(e):
             return jsonify({"error": f"User {user_id} not found"}), 404
        return jsonify({"error": f"Failed to delete user: {str(e)}"}), 500

@app.route('/api/admin/users/<user_id>/role', methods=['PUT'])
def admin_update_user_role(user_id):
    try:
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403

        data = request.get_json()
        new_role = data.get('role')
        allowed_roles = ['admin', 'user', 'agent']
        if not new_role or new_role not in allowed_roles:
             return jsonify({"error": f"Invalid or missing role. Must be one of: {', '.join(allowed_roles)}"}), 400

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE public.profiles SET role = %s WHERE id = %s",
                (new_role, user_id)
            )
            updated_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            if updated_rows == 0:
                 cursor = conn.cursor()
                 cursor.execute("SELECT 1 FROM public.profiles WHERE id = %s", (user_id,))
                 if not cursor.fetchone():
                     print(f"No profile found for {user_id}, creating one.")
                     cursor.execute("INSERT INTO public.profiles (id, role) VALUES (%s, %s)", (user_id, new_role))
                     conn.commit()
                     cursor.close()
                     return jsonify({"status": "success", "message": f"User {user_id} role created and set to {new_role}"}), 201
                 else:
                    cursor.close()
                    return jsonify({"error": f"User profile for {user_id} not found, but exists?"}), 404
            return jsonify({"status": "success", "message": f"User {user_id} role updated to {new_role}"}), 200
        except Exception as db_error:
             print(f"Error updating profile role for user {user_id}: {db_error}")
             if conn: conn.rollback()
             return jsonify({"error": f"Database error updating role: {str(db_error)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)

    except Exception as e:
        print(f"Error initiating update for user {user_id} role: {e}")
        if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
        if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# --- Agent Management Endpoints ---

@app.route('/api/agentes', methods=['GET'])
def get_agentes():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, nombre, email, telefono FROM public.agentes ORDER BY nombre ASC;")
        agentes = cursor.fetchall()
        cursor.close()
        return jsonify(agentes)
    except Exception as e:
        print(f"Error getting agentes: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/agentes', methods=['POST'])
def add_agente():
    try:
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403

        data = request.get_json()
        nombre = data.get('nombre')
        email = data.get('email')
        telefono = data.get('telefono')

        if not nombre or not email:
            return jsonify({"error": "Nombre and email are required"}), 400

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = """
                INSERT INTO public.agentes (nombre, email, telefono)
                VALUES (%s, %s, %s) RETURNING id;
            """
            cursor.execute(query, (nombre, email, telefono))
            new_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return jsonify({"status": "success", "id": new_id}), 201
        except psycopg2.IntegrityError as ie:
            conn.rollback()
            return jsonify({"error": f"Agent with email {email} might already exist. Details: {ie}"}), 409
        except Exception as e:
            if conn: conn.rollback()
            print(f"Error adding agente: {e}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)

    except Exception as e:
         print(f"Auth error during add_agente: {e}")
         if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
         if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
         return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/agentes/<int:id>', methods=['PUT'])
def update_agente(id):
    try:
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403

        data = request.get_json()
        nombre = data.get('nombre')
        email = data.get('email')
        telefono = data.get('telefono')

        if not nombre or not email:
            return jsonify({"error": "Nombre and email are required"}), 400

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = """
                UPDATE public.agentes SET nombre = %s, email = %s, telefono = %s
                WHERE id = %s;
            """
            cursor.execute(query, (nombre, email, telefono, id))
            updated_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            if updated_rows == 0:
                return jsonify({"error": "Agent not found"}), 404
            return jsonify({"status": "success"})
        except psycopg2.IntegrityError as ie:
            conn.rollback()
            return jsonify({"error": f"Email {email} might already be in use. Details: {ie}"}), 409
        except Exception as e:
            if conn: conn.rollback()
            print(f"Error updating agente {id}: {e}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)

    except Exception as e:
         print(f"Auth error during update_agente {id}: {e}")
         if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
         if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
         return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/api/agentes/<int:id>', methods=['DELETE'])
def delete_agente(id):
    try:
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM propiedades
                WHERE agente_id = %s
                   OR captado_por_agente_id = %s
                   OR validado_por_usuario_id = %s
                LIMIT 1
            """, (id, id, id))
            if cursor.fetchone():
                 cursor.close()
                 return jsonify({"error": "Cannot delete agent: referenced in 'propiedades' table"}), 409

            cursor.execute("DELETE FROM public.agentes WHERE id = %s;", (id,))
            deleted_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            if deleted_rows == 0:
                 return jsonify({"error": "Agent not found"}), 404
            return jsonify({"status": "deleted"})
        except Exception as e:
            if conn: conn.rollback()
            print(f"Error deleting agente {id}: {e}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        finally:
            if conn:
                return_db_connection(conn)

    except Exception as e:
         print(f"Auth error during delete_agente {id}: {e}")
         if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
         if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
         return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    
    
@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Obtiene estadísticas generales del dashboard"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        stats = {}
        
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM propiedades 
            WHERE deleted_at IS NULL
        """)
        stats['total_propiedades'] = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM propiedades p
            JOIN estados_publicacion ep ON p.estado_publicacion_id = ep.id
            WHERE p.deleted_at IS NULL 
            AND ep.nombre ILIKE '%publicad%'
        """)
        stats['propiedades_publicadas'] = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COALESCE(SUM(visitas), 0) as total 
            FROM propiedades 
            WHERE deleted_at IS NULL
        """)
        stats['total_visitas'] = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT id, titulo, visitas, direccion
            FROM propiedades 
            WHERE deleted_at IS NULL AND visitas > 0
            ORDER BY visitas DESC 
            LIMIT 1
        """)
        most_visited = cursor.fetchone()
        stats['propiedad_mas_visitada'] = dict(most_visited) if most_visited else None
        
        cursor.execute("""
            SELECT tn.nombre, COUNT(p.id) as cantidad
            FROM tipos_negocio tn
            LEFT JOIN propiedades p ON p.tipo_negocio_id = tn.id AND p.deleted_at IS NULL
            GROUP BY tn.id, tn.nombre
            ORDER BY cantidad DESC
        """)
        stats['por_tipo_negocio'] = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT tp.nombre, COUNT(p.id) as cantidad
            FROM tipos_propiedad tp
            LEFT JOIN propiedades p ON p.tipo_propiedad_id = tp.id AND p.deleted_at IS NULL
            GROUP BY tp.id, tp.nombre
            ORDER BY cantidad DESC
        """)
        stats['por_tipo_propiedad'] = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT ep.nombre, COUNT(p.id) as cantidad
            FROM estados_publicacion ep
            LEFT JOIN propiedades p ON p.estado_publicacion_id = ep.id AND p.deleted_at IS NULL
            GROUP BY ep.id, ep.nombre
            ORDER BY cantidad DESC
        """)
        stats['por_estado_publicacion'] = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT c.nombre as ciudad, e.nombre as estado, COUNT(p.id) as cantidad
            FROM ciudades c
            LEFT JOIN propiedades p ON p.ciudad_id = c.id AND p.deleted_at IS NULL
            LEFT JOIN estados e ON c.estado_id = e.id
            GROUP BY c.id, c.nombre, e.nombre
            HAVING COUNT(p.id) > 0
            ORDER BY cantidad DESC
            LIMIT 5
        """)
        stats['top_ciudades'] = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT a.nombre, a.email, COUNT(p.id) as propiedades_captadas
            FROM agentes a
            LEFT JOIN propiedades p ON p.captado_por_agente_id = a.id AND p.deleted_at IS NULL
            GROUP BY a.id, a.nombre, a.email
            HAVING COUNT(p.id) > 0
            ORDER BY propiedades_captadas DESC
            LIMIT 5
        """)
        stats['top_agentes'] = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT 
                ROUND(AVG(precio), 2) as precio_promedio_venta,
                ROUND(AVG(precio_alquiler), 2) as precio_promedio_alquiler,
                MIN(precio) as precio_min_venta,
                MAX(precio) as precio_max_venta,
                MIN(precio_alquiler) as precio_min_alquiler,
                MAX(precio_alquiler) as precio_max_alquiler
            FROM propiedades 
            WHERE deleted_at IS NULL
        """)
        precios = cursor.fetchone()
        stats['precios'] = dict(precios) if precios else None
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM propiedades 
            WHERE deleted_at IS NULL 
            AND created_at >= NOW() - INTERVAL '7 days'
        """)
        stats['propiedades_nuevas_semana'] = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT CASE WHEN pi.id IS NOT NULL THEN p.id END) as con_imagenes,
                COUNT(DISTINCT CASE WHEN pi.id IS NULL THEN p.id END) as sin_imagenes
            FROM propiedades p
            LEFT JOIN propiedades_imagenes pi ON p.id = pi.propiedad_id
            WHERE p.deleted_at IS NULL
        """)
        imagenes_stats = cursor.fetchone()
        stats['imagenes'] = dict(imagenes_stats) if imagenes_stats else None
        
        cursor.close()
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error obteniendo estadísticas del dashboard: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)


@app.route('/api/dashboard/recent-activity', methods=['GET'])
def get_recent_activity():
    """Obtiene actividad reciente (últimas 10 propiedades modificadas)"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                p.id,
                p.titulo,
                p.created_at,
                p.updated_at,
                a.nombre as captado_por,
                ep.nombre as estado
            FROM propiedades p
            LEFT JOIN agentes a ON p.captado_por_agente_id = a.id
            LEFT JOIN estados_publicacion ep ON p.estado_publicacion_id = ep.id
            WHERE p.deleted_at IS NULL
            ORDER BY COALESCE(p.updated_at, p.created_at) DESC
            LIMIT 10
        """)
        
        recent = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        
        for item in recent:
            if item.get('created_at'):
                item['created_at'] = item['created_at'].isoformat()
            if item.get('updated_at'):
                item['updated_at'] = item['updated_at'].isoformat()
        
        return jsonify(recent)
        
    except Exception as e:
        print(f"Error obteniendo actividad reciente: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')