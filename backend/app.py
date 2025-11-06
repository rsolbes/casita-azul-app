import os
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor # Added for is_admin
from flask import Flask, jsonify, request # request was already here, ensure RealDictCursor is imported
from flask_cors import CORS
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
origins = [
    "http://localhost:4200",  # Tu app de admin
    "http://localhost:50687", # Tu otra app
    "http://127.0.0.1:4200",   # A veces es necesario agregar 127.0.0.1 también
    "http://127.0.0.1:50687"
]
CORS(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=True)


# Configuración de Supabase
SUPABASE_URL = "https://izozjytmktbuhpttczid.supabase.co" # Reemplaza si es diferente
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# --- Add Admin Client ---
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") # Asegúrate de tener esto en .env
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# Configuración de Storage
BUCKET_NAME = "imagenes casas" # Asegúrate que este sea el nombre correcto de tu bucket
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Conexión a Base de Datos (directa para operaciones específicas)
def get_db_connection():
    conn = psycopg2.connect(
        user=os.getenv("DB_USER", "postgres.izozjytmktbuhpttczid"),
        password=os.getenv("PASSWORD", "bddingsoftware123"), # Asegúrate que esto esté en tu .env real
        host=os.getenv("HOST", "aws-1-us-east-2.pooler.supabase.com"),
        port=os.getenv("PORT", "6543"),
        dbname=os.getenv("DBNAME", "postgres"),
        sslmode='require'
    )
    return conn

# --- Funciones Auxiliares para Roles de Admin ---
def get_user_id_from_token(request):
    """Extrae el user ID del token de autorización."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise Exception("No token provided")
    token = auth_header.split(' ')[1]
    # Use the regular (anon key) client to verify the token initially
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
         raise Exception("Invalid token")
    return user_response.user.id

def is_admin(user_id: str) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Query the profiles table to get the role
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
            conn.close()
# --- End Helper Functions ---


@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'user') # Get role from request, default to 'user'

        # Use Supabase Auth for registration
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        # --- Set the role in public.profiles ---
        # Note: This happens AFTER signup. Consider a trigger or edge function for atomicity.
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
                # Log this error, user exists but profile might not be set correctly
            finally:
                if conn:
                    conn.close()
        # --- End Role Setting ---

        return jsonify({
            "status": "success",
            "message": "Usuario registrado. Revisa tu email para confirmar."
        }), 201

    except Exception as e:
        print(f"Error en registro: {e}")
        # Consider more specific error handling based on Supabase exceptions
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

        # Use Supabase Auth for login
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        return jsonify({
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email
                # You might want to fetch and include the role here as well
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
        # It's better to invalidate the token provided by the client
        auth_header = request.headers.get('Authorization')
        token = None
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if token:
            supabase.auth.sign_out(token) # Pass the specific token to sign out
        else:
             # Fallback if no token provided (less secure, depends on Supabase client state)
             supabase.auth.sign_out()

        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error en logout: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/api/user', methods=['GET', 'OPTIONS'])
def get_user():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "No token provided"}), 401

        token = auth_header.split(' ')[1]
        user_response = supabase.auth.get_user(token)
        user = user_response.user

        # Fetch role from profiles table
        role = 'user' # Default role
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
                conn.close()


        return jsonify({
            "id": user.id,
            "email": user.email,
            "role": role # Include the role
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

        response = supabase.auth.refresh_session(refresh_token)

        # Check if response.session is None which indicates an error
        if not response.session:
             # Attempt to extract error details if available from Supabase client's error handling
             error_message = "Invalid refresh token or session expired"
             # In newer versions, the error might be raised directly,
             # so this check might not be needed if the outer try/except catches it.
             return jsonify({"error": error_message}), 401


        return jsonify({
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token # Supabase might issue a new refresh token
        }), 200

    except Exception as e:
        print(f"Error en refresh: {e}")
        # Be more specific if possible based on Supabase client errors
        return jsonify({"error": "Failed to refresh token: " + str(e)}), 401


# --- Endpoint de Catálogos ---
@app.route('/api/catalogos', methods=['GET'])
def get_catalogos():
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
            # Handle 'agentes' separately if it needs more columns
            if tabla == 'agentes':
                cursor.execute("SELECT id, nombre, email, telefono FROM public.agentes ORDER BY nombre ASC;")
            else:
                cursor.execute(f"SELECT id, nombre FROM public.{tabla} ORDER BY nombre ASC;")
            catalogos[tabla] = cursor.fetchall()

        cursor.close()
        return jsonify(catalogos)

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

# --- Endpoints de Propiedades ---
@app.route('/api/propiedades', methods=['GET'])
def get_properties():
    conn = None
    try:
        # --- INICIO DE CAMBIOS ---
        # 1. Obtener parámetros de filtro de la URL
        tipo_negocio_id = request.args.get('tipo_negocio_id')
        
        # Cambiamos 'ne' (Not Equal) por 'not_in' (No incluir)
        # Esperará un string de IDs separados por coma, ej: "2,3,4"
        estado_publicacion_id_not_in_str = request.args.get('estado_publicacion_id__not_in') 

        # 2. Construir la consulta base (sin cambios)
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

        # 3. Preparar filtros y parámetros
        filters = ["p.deleted_at IS NULL"] # Siempre excluir borrados lógicos
        params = []

        # Añadir filtro por tipo_negocio_id si se proporciona
        if tipo_negocio_id:
            filters.append("p.tipo_negocio_id = %s")
            params.append(tipo_negocio_id)

        # Añadir filtro para excluir una LISTA de estados de publicación
        if estado_publicacion_id_not_in_str:
            try:
                # Convertir el string "2,3,4" en una tupla de enteros (2, 3, 4)
                excluded_ids = tuple(int(id) for id in estado_publicacion_id_not_in_str.split(','))
                if excluded_ids:
                    # Usar el operador 'NOT IN' de SQL
                    # '%s' aquí se expandirá a la tupla de IDs
                    filters.append("p.estado_publicacion_id NOT IN %s")
                    params.append(excluded_ids)
            except ValueError:
                # Ignorar el filtro si no es válido (ej. "a,b,c")
                print(f"Filtro 'estado_publicacion_id__not_in' inválido: {estado_publicacion_id_not_in_str}")


        # 4. Añadir filtros a la consulta
        if filters:
            query += " WHERE " + " AND ".join(filters)

        # 5. Añadir GROUP BY y ORDER BY (sin cambios)
        query += """
            GROUP BY p.id
            ORDER BY p.id DESC;
        """
        # --- FIN DE CAMBIOS ---

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Ejecutar la consulta con los parámetros (importante pasar params como tupla)
        cursor.execute(query, tuple(params))
        propiedades = cursor.fetchall()
        cursor.close()
        return jsonify({"properties": propiedades})
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:id>', methods=['GET'])
def get_property(id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener propiedad específica con sus imágenes
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
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades', methods=['POST'])
def add_property():
    # ADD ROLE CHECK HERE if needed (e.g., only agents or admins can add)
    # try:
    #     requesting_user_id = get_user_id_from_token(request)
    #     if not is_admin(requesting_user_id): # Or check for 'agent' role
    #          return jsonify({"error": "Permission denied"}), 403
    # except Exception as auth_e:
    #      return jsonify({"error": str(auth_e)}), 401

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
        print(e)
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:id>', methods=['PUT'])
def update_property(id):
    # ADD ROLE CHECK HERE
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
        print(e)
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:id>', methods=['DELETE'])
def delete_property(id):
    # ADD ROLE CHECK HERE
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
        print(e)
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

# --- Endpoints de Imágenes ---
@app.route('/api/propiedades/<int:propiedad_id>/imagenes', methods=['POST'])
def upload_image(propiedad_id):
    """Subir una imagen a Supabase Storage y guardar referencia en BD"""
    # ADD ROLE CHECK HERE

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
        # Generar nombre único para el archivo
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{propiedad_id}_{uuid.uuid4().hex}.{file_extension}"
        file_path = f"propiedades/{unique_filename}"

        # Leer el archivo
        file_content = file.read()

        # Subir a Supabase Storage
        supabase.storage.from_(BUCKET_NAME).upload(
            file_path,
            file_content,
            file_options={"content-type": file.content_type}
        )

        # Obtener URL pública
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)

        # Guardar referencia en la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        # Si es principal, desmarcar otras imágenes como principal
        if es_principal:
            cursor.execute(
                "UPDATE propiedades_imagenes SET es_principal = FALSE WHERE propiedad_id = %s;",
                (propiedad_id,)
            )

        # Obtener el siguiente orden
        cursor.execute(
            "SELECT COALESCE(MAX(orden), -1) + 1 FROM propiedades_imagenes WHERE propiedad_id = %s;",
            (propiedad_id,)
        )
        orden = cursor.fetchone()[0]

        # Insertar registro de imagen
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
        print(e)
        if conn: conn.rollback()
        # Consider deleting from storage if DB insert fails
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:propiedad_id>/imagenes/<int:imagen_id>', methods=['DELETE'])
def delete_image(propiedad_id, imagen_id):
    """Eliminar imagen de Supabase Storage y BD"""
    # ADD ROLE CHECK HERE
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener información de la imagen
        cursor.execute(
            "SELECT nombre_archivo FROM propiedades_imagenes WHERE id = %s AND propiedad_id = %s;",
            (imagen_id, propiedad_id)
        )
        imagen = cursor.fetchone()

        if not imagen:
            cursor.close()
            return jsonify({"error": "Imagen no encontrada"}), 404

        # Eliminar de Supabase Storage
        file_path = f"propiedades/{imagen['nombre_archivo']}"
        try:
            supabase.storage.from_(BUCKET_NAME).remove([file_path])
        except Exception as storage_e:
            # Log error but continue to delete DB record
            print(f"Error deleting from storage (continuing): {storage_e}")


        # Eliminar de la base de datos
        cursor.execute(
            "DELETE FROM propiedades_imagenes WHERE id = %s;",
            (imagen_id,)
        )
        deleted_rows = cursor.rowcount
        conn.commit()
        cursor.close()

        if deleted_rows == 0:
             # Should not happen if fetchone worked, but good practice
             return jsonify({"error": "Imagen no encontrada en DB"}), 404

        return jsonify({"status": "deleted"})

    except Exception as e:
        print(e)
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:propiedad_id>/imagenes/<int:imagen_id>/principal', methods=['PUT'])
def set_principal_image(propiedad_id, imagen_id):
    """Marcar una imagen como principal"""
    # ADD ROLE CHECK HERE
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Use a transaction
        # Desmarcar todas las imágenes como principal for this property
        cursor.execute(
            "UPDATE propiedades_imagenes SET es_principal = FALSE WHERE propiedad_id = %s;",
            (propiedad_id,)
        )

        # Marcar la imagen especificada como principal
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
        print(e)
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# --- START: User Management Endpoints (Admin Only) ---

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
            
            # Esta consulta une auth.users con public.profiles
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
            
            # Convertir UUIDs y datetimes a string para jsonify
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
                conn.close()
    except Exception as e:
        print(f"Error listing users: {e}")
        # Differentiate between auth errors (401/403) and server errors (500)
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
        role = data.get('role', 'user') # Default role if not provided

        if not email or not password:
             return jsonify({"error": "Email and password required"}), 400

        # Create user using admin client
        response = supabase_admin.auth.admin.create_user({
             "email": email,
             "password": password,
             "email_confirm": True # Automatically confirm email for admin-created users
        })
        new_user = response.user

        # --- IMPORTANT: Set the role in your public.profiles table ---
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
             # If profile insert fails, DELETE the user we just created in auth.users
             print(f"Error inserting profile for new user {new_user.id}. Attempting to delete auth user. Error: {db_error}")
             try:
                 supabase_admin.auth.admin.delete_user(new_user.id)
                 print(f"Successfully deleted auth user {new_user.id} after profile insert failure.")
             except Exception as delete_error:
                 print(f"CRITICAL: Failed to delete auth user {new_user.id} after profile insert failure. Manual cleanup needed. Error: {delete_error}")
             # Return error to client
             return jsonify({"error": f"Failed to set user role in profile: {db_error}"}), 500
        finally:
            if conn:
                conn.close()
        # --- End Role Setting ---

        return jsonify(new_user.model_dump()), 201 # Usa model_dump() en lugar de dict()
    except Exception as e:
        print(f"Error creating user: {e}")
        # Check for specific Supabase errors if possible (e.g., duplicate email)
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

        # Prevent admin from deleting themselves?
        if str(requesting_user_id) == str(user_id):
             return jsonify({"error": "Cannot delete your own admin account"}), 400


        # Delete user using admin client
        # This automatically cascades to your profiles table due to ON DELETE CASCADE
        supabase_admin.auth.admin.delete_user(user_id)

        return jsonify({"status": "success", "message": f"User {user_id} deleted"}), 200
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
        if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
        # Check if user not found error from Supabase
        if "User not found" in str(e): # Adjust based on actual Supabase error message
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
        # Add validation for allowed roles if needed
        allowed_roles = ['admin', 'user', 'agent'] # Example
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
                 # Check if profile exists, if not, create it
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
                    return jsonify({"error": f"User profile for {user_id} not found, but exists?"}), 404 # Should not happen
            return jsonify({"status": "success", "message": f"User {user_id} role updated to {new_role}"}), 200
        except Exception as db_error:
             print(f"Error updating profile role for user {user_id}: {db_error}")
             if conn: conn.rollback()
             return jsonify({"error": f"Database error updating role: {str(db_error)}"}), 500
        finally:
            if conn:
                conn.close()

    except Exception as e:
        print(f"Error initiating update for user {user_id} role: {e}")
        if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
        if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# --- END: User Management Endpoints ---


# --- START: Agent Management Endpoints (Admin Only for CUD) ---

@app.route('/api/agentes', methods=['GET'])
def get_agentes():
    # Keep this public or add role check if needed (e.g., only logged-in users?)
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
            conn.close()

@app.route('/api/agentes', methods=['POST'])
def add_agente():
    try:
        # --- Admin Check ---
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403
        # --- End Admin Check ---

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
        except psycopg2.IntegrityError as ie: # Catch unique constraint violation
            conn.rollback()
            return jsonify({"error": f"Agent with email {email} might already exist. Details: {ie}"}), 409
        except Exception as e:
            if conn: conn.rollback()
            print(f"Error adding agente: {e}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()

    except Exception as e: # Catch errors from get_user_id_from_token or is_admin
         print(f"Auth error during add_agente: {e}")
         if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
         if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
         return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/agentes/<int:id>', methods=['PUT'])
def update_agente(id):
    try:
        # --- Admin Check ---
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403
        # --- End Admin Check ---

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
        except psycopg2.IntegrityError as ie: # Catch unique constraint violation
            conn.rollback()
            return jsonify({"error": f"Email {email} might already be in use. Details: {ie}"}), 409
        except Exception as e:
            if conn: conn.rollback()
            print(f"Error updating agente {id}: {e}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()

    except Exception as e: # Catch errors from get_user_id_from_token or is_admin
         print(f"Auth error during update_agente {id}: {e}")
         if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
         if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
         return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/api/agentes/<int:id>', methods=['DELETE'])
def delete_agente(id):
    try:
        # --- Admin Check ---
        requesting_user_id = get_user_id_from_token(request)
        if not is_admin(requesting_user_id):
            return jsonify({"error": "Admin privileges required"}), 403
        # --- End Admin Check ---

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Check if agent is referenced before deleting
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
                conn.close()

    except Exception as e: # Catch errors from get_user_id_from_token or is_admin
         print(f"Auth error during delete_agente {id}: {e}")
         if "Invalid token" in str(e) or "No token provided" in str(e):
             return jsonify({"error": str(e)}), 401
         if "Admin privileges required" in str(e):
              return jsonify({"error": str(e)}), 403
         return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# --- END: Agent Management Endpoints ---


if __name__ == '__main__':
    # Consider using a more production-ready server like Gunicorn/Waitress
    # and disabling debug mode for production
    app.run(debug=True, host='0.0.0.0') # Listen on all interfaces if running in Docker/cloud