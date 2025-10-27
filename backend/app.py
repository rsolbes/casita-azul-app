import os
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Configuración de Supabase Storage
SUPABASE_URL = "https://izozjytmktbuhpttczid.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET_NAME = "imagenes casas"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = psycopg2.connect(
        user=os.getenv("DB_USER", "postgres.izozjytmktbuhpttczid"),
        password=os.getenv("PASSWORD", "bddingsoftware123"),
        host=os.getenv("HOST", "aws-1-us-east-2.pooler.supabase.com"),
        port=os.getenv("PORT", "6543"),
        dbname=os.getenv("DBNAME", "postgres"),
        sslmode='require'
    )
    return conn

@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        # Use Supabase Auth for registration
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        return jsonify({
            "status": "success",
            "message": "Usuario registrado. Revisa tu email para confirmar."
        }), 201
        
    except Exception as e:
        print(f"Error en registro: {e}")
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
        user = supabase.auth.get_user(token)
        
        return jsonify({
            "id": user.user.id,
            "email": user.user.email
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
        
        response = supabase.auth.refresh_session(refresh_token)
        
        return jsonify({
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }), 200
        
    except Exception as e:
        print(f"Error en refresh: {e}")
        return jsonify({"error": str(e)}), 401

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
            cursor.execute(f"SELECT id, nombre FROM public.{tabla} ORDER BY nombre ASC;")
            catalogos[tabla] = cursor.fetchall()
            
        cursor.execute("SELECT id, nombre, email, telefono FROM public.agentes ORDER BY nombre ASC;")
        catalogos['agentes'] = cursor.fetchall()

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
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener propiedades con sus imágenes
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
            WHERE p.deleted_at IS NULL
            GROUP BY p.id
            ORDER BY p.id DESC;
        """
        cursor.execute(query)
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
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

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
        
        conn.commit()
        cursor.close()
        return jsonify({"status": "success"})
        
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:id>', methods=['DELETE'])
def delete_property(id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE propiedades SET deleted_at = NOW() WHERE id = %s;", (id,))
        conn.commit()
        cursor.close()
        return jsonify({"status": "deleted (soft)"})
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

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
            "nombre_archivo": unique_filename
        }), 201
        
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:propiedad_id>/imagenes/<int:imagen_id>', methods=['DELETE'])
def delete_image(propiedad_id, imagen_id):
    """Eliminar imagen de Supabase Storage y BD"""
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
            return jsonify({"error": "Imagen no encontrada"}), 404
        
        # Eliminar de Supabase Storage
        file_path = f"propiedades/{imagen['nombre_archivo']}"
        supabase.storage.from_(BUCKET_NAME).remove([file_path])
        
        # Eliminar de la base de datos
        cursor.execute(
            "DELETE FROM propiedades_imagenes WHERE id = %s;",
            (imagen_id,)
        )
        
        conn.commit()
        cursor.close()
        return jsonify({"status": "deleted"})
        
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/propiedades/<int:propiedad_id>/imagenes/<int:imagen_id>/principal', methods=['PUT'])
def set_principal_image(propiedad_id, imagen_id):
    """Marcar una imagen como principal"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Desmarcar todas las imágenes como principal
        cursor.execute(
            "UPDATE propiedades_imagenes SET es_principal = FALSE WHERE propiedad_id = %s;",
            (propiedad_id,)
        )
        
        # Marcar la imagen especificada como principal
        cursor.execute(
            "UPDATE propiedades_imagenes SET es_principal = TRUE WHERE id = %s AND propiedad_id = %s;",
            (imagen_id, propiedad_id)
        )
        
        conn.commit()
        cursor.close()
        return jsonify({"status": "success"})
        
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)