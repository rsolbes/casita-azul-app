import os
import psycopg2
from psycopg2.extras import RealDictCursor # ¡Muy importante para convertir filas a dict!
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Configuración de la Base de Datos ---

def get_db_connection():
    # Usamos los valores por defecto que me diste, pero priorizamos variables de entorno
    conn = psycopg2.connect(
        user=os.getenv("DB_USER", "postgres.izozjytmktbuhpttczid"),
        password=os.getenv("PASSWORD", "bddingsoftware123"),
        host=os.getenv("HOST", "aws-1-us-east-2.pooler.supabase.com"),
        port=os.getenv("PORT", "6543"),
        dbname=os.getenv("DBNAME", "postgres"),
        sslmode='require'
    )
    return conn

# --- Endpoint de Catálogos ---

@app.route('/api/catalogos', methods=['GET'])
def get_catalogos():
    """
    Endpoint para obtener todos los datos necesarios para los dropdowns (selects).
    """
    catalogos = {}
    conn = None
    try:
        conn = get_db_connection()
        # Usamos RealDictCursor para que los resultados ya sean listas de diccionarios
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Lista de tablas de catálogo que queremos
        tablas_catalogo = [
            'agentes', 'agentes_externos', 'ciudades', 'estados', 
            'estados_fisicos', 'estados_publicacion', 'frecuencias_alquiler',
            'monedas', 'tipos_negocio', 'tipos_propiedad', 'zonas'
        ]
        
        for tabla in tablas_catalogo:
            cursor.execute(f"SELECT id, nombre FROM public.{tabla} ORDER BY nombre ASC;")
            catalogos[tabla] = cursor.fetchall()
            
        # Para agentes, podríamos querer más datos
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

# --- Endpoints de Propiedades (CRUD Completo) ---

@app.route('/api/propiedades', methods=['GET'])
def get_properties():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Seleccionamos todas las propiedades que NO estén borradas lógicamente
        cursor.execute("SELECT * FROM propiedades WHERE deleted_at IS NULL ORDER BY id ASC;")
        propiedades = cursor.fetchall()
        cursor.close()
        # Envolvemos en un objeto para consistencia
        return jsonify({"properties": propiedades})
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
        
        # SQL con TODOS los campos. data.get() devuelve None si la llave no existe
        # Nota: created_at y updated_at se manejan con defaults en la DB
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
        
        # Query de actualización con todos los campos y updated_at
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
    """
    Implementa borrado lógico (soft delete) actualizando deleted_at.
    """
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


if __name__ == '__main__':
    app.run(debug=True)