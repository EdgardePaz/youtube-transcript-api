from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import re
import json

app = Flask(__name__)
CORS(app)

def obtener_subtitulos_directo(video_id):
    """Obtiene subtítulos directamente sin usar yt-dlp"""
    import requests
    import xml.etree.ElementTree as ET
    
    # URL de la API de subtítulos de YouTube
    base_url = "https://www.youtube.com/api/timedtext"
    
    # Primero, obtiene la lista de idiomas disponibles
    params = {
        'v': video_id,
        'type': 'list'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'es-ES,es;q=0.9'
    }
    
    try:
        # Lista de idiomas
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None, None, None
        
        # Parsea XML de idiomas disponibles
        root = ET.fromstring(response.text)
        
        # Busca español
        idiomas_espanol = ['es', 'es-ES', 'es-MX', 'es-419']
        lang_code = None
        lang_name = None
        
        for track in root.findall('.//track'):
            lang = track.get('lang_code', '')
            if lang in idiomas_espanol:
                lang_code = lang
                lang_name = track.get('name', 'Español')
                break
        
        if not lang_code:
            return None, None, None
        
        # Descarga los subtítulos en ese idioma
        params = {
            'v': video_id,
            'lang': lang_code,
            'fmt': 'srv3'  # Formato XML simple
        }
        
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None, None, None
        
        # Parsea el XML de subtítulos
        root = ET.fromstring(response.text)
        textos = []
        
        for text_elem in root.findall('.//text'):
            texto = text_elem.text
            if texto:
                textos.append(texto.strip())
        
        texto_completo = ' '.join(textos)
        
        return texto_completo, lang_code, lang_name
        
    except Exception as e:
        print(f"❌ Error en obtener_subtitulos_directo: {e}")
        return None, None, None
    
def obtener_subtitulos_rapidapi(video_id):
    """Obtiene subtítulos usando RapidAPI"""
    import requests
    
    url = "https://youtube-transcript3.p.rapidapi.com/transcript"
    
    querystring = {
        "video_id": video_id,
        "lang": "es"
    }
    
    headers = {
        "X-RapidAPI-Key": "4db8764539mshfca57004d418dd6p1f779ajsn94d62ab586d8",  # <-- REEMPLAZA ESTO
        "X-RapidAPI-Host": "youtube-transcript3.p.rapidapi.com"
    }
    
    try:
        print("🌐 Intentando con RapidAPI...")
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # El formato puede variar según el API
            if 'transcript' in data:
                # Une todo el texto
                texto_completo = ' '.join([item.get('text', '') for item in data['transcript']])
                return texto_completo, 'es', 'RapidAPI'
            elif 'text' in data:
                return data['text'], 'es', 'RapidAPI'
            elif isinstance(data, list):
                texto_completo = ' '.join([item.get('text', '') for item in data])
                return texto_completo, 'es', 'RapidAPI'
        
        print(f"❌ RapidAPI respondió con código: {response.status_code}")
        return None, None, None
        
    except Exception as e:
        print(f"❌ Error con RapidAPI: {e}")
        return None, None, None

@app.route('/')
def inicio():
    return jsonify({
        'mensaje': '✅ El servidor está funcionando',
        'endpoints': {
            '/transcript': 'Obtener transcripción (params: video_id)',
            '/check': 'Verificar idiomas disponibles (params: video_id)'
        }
    })

@app.route('/check')
def verificar_idiomas():
    video_id = request.args.get('video_id')
    
    if not video_id:
        return jsonify({'error': 'Necesitas proporcionar un video_id'}), 400
    
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            subtitulos_manuales = list(info.get('subtitles', {}).keys())
            subtitulos_auto = list(info.get('automatic_captions', {}).keys())
            
            return jsonify({
                'video_id': video_id,
                'titulo': info.get('title', 'Sin título'),
                'subtitulos_manuales': subtitulos_manuales,
                'subtitulos_automaticos': subtitulos_auto,
                'tiene_espanol_manual': any('es' in s for s in subtitulos_manuales),
                'tiene_espanol_auto': any('es' in s for s in subtitulos_auto)
            })
    
    except Exception as error:
        return jsonify({'error': str(error)}), 500

def limpiar_texto_subtitulos(texto):
    """Limpia el texto de subtítulos removiendo etiquetas y formatos"""
    # Remueve etiquetas HTML/XML
    texto = re.sub(r'<[^>]+>', '', texto)
    # Remueve timestamps (formato 00:00:00.000)
    texto = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}', '', texto)
    # Remueve números de línea
    texto = re.sub(r'^\d+\s*$', '', texto, flags=re.MULTILINE)
    # Remueve líneas vacías múltiples
    texto = re.sub(r'\n\s*\n+', '\n', texto)
    # Remueve espacios múltiples
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def parsear_json3(data):
    """Parsea formato JSON3 de YouTube"""
    try:
        json_data = json.loads(data)
        textos = []
        
        # Intenta diferentes estructuras de JSON3
        if 'events' in json_data:
            for event in json_data.get('events', []):
                # Estructura con segs
                if 'segs' in event:
                    for seg in event['segs']:
                        if 'utf8' in seg:
                            textos.append(seg['utf8'])
                # Estructura directa con texto
                elif 'text' in event:
                    textos.append(event['text'])
        
        # Si no encontró nada, busca recursivamente
        if not textos:
            def extraer_texto_recursivo(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key in ['utf8', 'text', 'simpleText']:
                            if isinstance(value, str):
                                textos.append(value)
                        else:
                            extraer_texto_recursivo(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extraer_texto_recursivo(item)
            
            extraer_texto_recursivo(json_data)
        
        texto_final = ' '.join(textos)
        # Limpia caracteres especiales de YouTube
        texto_final = texto_final.replace('\n', ' ')
        texto_final = re.sub(r'\s+', ' ', texto_final)
        return texto_final.strip()
    except Exception as e:
        print(f"❌ Error parseando JSON3: {e}")
        return None

def parsear_srv3(data):
    """Parsea formato SRV3 (XML) de YouTube"""
    try:
        # Extrae texto entre tags <text>
        textos = re.findall(r'<text[^>]*>(.*?)</text>', data, re.DOTALL)
        texto_limpio = ' '.join(textos)
        return limpiar_texto_subtitulos(texto_limpio)
    except:
        return None

def parsear_vtt(data):
    """Parsea formato VTT"""
    try:
        # Remueve header WEBVTT
        texto = re.sub(r'^WEBVTT.*?\n\n', '', data, flags=re.DOTALL)
        return limpiar_texto_subtitulos(texto)
    except:
        return None

@app.route('/transcript')
def obtener_transcripcion():
    video_id = request.args.get('video_id')
    
    if not video_id:
        return jsonify({
            'exito': False,
            'error': 'Necesitas proporcionar un video_id'
        }), 400
    
    try:
        print(f"📹 Obteniendo transcripción de: {video_id}")
        
                # Intenta método directo primero
        print("🔄 Intentando método directo de API...")
        texto_directo, idioma, nombre_idioma = obtener_subtitulos_directo(video_id)
        
        # Si el método directo detecta bloqueo de Google
        if texto_directo and 'sorry' in texto_directo.lower():
            print("⚠️ Google bloqueó el método directo, intentando RapidAPI...")
            texto_directo = None
        
        # Si falló el método directo, intenta RapidAPI
        if not texto_directo or len(texto_directo) < 50:
            texto_rapid, idioma_rapid, metodo_rapid = obtener_subtitulos_rapidapi(video_id)
            if texto_rapid and len(texto_rapid) > 50:
                print(f"✅ Subtítulos obtenidos vía RapidAPI: {len(texto_rapid)} caracteres")
                return jsonify({
                    'exito': True,
                    'video_id': video_id,
                    'transcripcion': texto_rapid,
                    'total_caracteres': len(texto_rapid),
                    'tipo_subtitulos': 'API externa',
                    'idioma': idioma_rapid,
                    'metodo': metodo_rapid
                })
        
        # Si el método directo funcionó
        if texto_directo and len(texto_directo) > 50:
            print(f"✅ Subtítulos obtenidos directamente: {len(texto_directo)} caracteres")
            return jsonify({
                'exito': True,
                'video_id': video_id,
                'transcripcion': texto_directo,
                'total_caracteres': len(texto_directo),
                'tipo_subtitulos': 'API directa',
                'idioma': idioma,
                'metodo': 'youtube_api_timedtext'
            })
        
        print("⚠️ Método directo falló, intentando con yt-dlp...")
        
        # Continúa con yt-dlp
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Configuración mejorada para Railway
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['es', 'es-ES', 'es-MX', 'es-419'],
            'quiet': False,
            'no_warnings': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash']
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("🔍 Extrayendo información del video...")
            info = ydl.extract_info(url, download=False)
            
            subtitulos_manuales = info.get('subtitles', {})
            subtitulos_auto = info.get('automatic_captions', {})
            
            print(f"📋 Subtítulos manuales disponibles: {list(subtitulos_manuales.keys())}")
            print(f"📋 Subtítulos automáticos disponibles: {list(subtitulos_auto.keys())}")
            
            # Busca subtítulos en español
            sub_data = None
            tipo = None
            idioma_usado = None
            
            idiomas_espanol = ['es', 'es-ES', 'es-MX', 'es-419', 'es-US']
            
            # Intenta manuales primero
            for lang in idiomas_espanol:
                if lang in subtitulos_manuales:
                    print(f"✓ Encontrados subtítulos manuales en {lang}")
                    try:
                        sub_list = subtitulos_manuales[lang]
                        # Busca el formato más fácil de parsear
                        for sub_format in sub_list:
                            if 'data' in sub_format:
                                sub_data = sub_format['data']
                                break
                        
                        if not sub_data:
                            # Descarga manualmente
                            import requests
                            sub_url = sub_list[0]['url']
                            response = requests.get(sub_url, timeout=30)
                            sub_data = response.text
                        
                        tipo = 'manual'
                        idioma_usado = lang
                        break
                    except Exception as e:
                        print(f"⚠️ Error con subtítulos manuales {lang}: {e}")
                        continue
            
            # Si no hay manuales, intenta automáticos
            if not sub_data:
                for lang in idiomas_espanol:
                    if lang in subtitulos_auto:
                        print(f"✓ Encontrados subtítulos automáticos en {lang}")
                        try:
                            sub_list = subtitulos_auto[lang]
                            
                            if 'data' in sub_list[0]:
                                sub_data = sub_list[0]['data']
                            else:
                                import requests
                                sub_url = sub_list[0]['url']
                                response = requests.get(sub_url, timeout=30)
                                sub_data = response.text
                            
                            tipo = 'automático'
                            idioma_usado = lang
                            break
                        except Exception as e:
                            print(f"⚠️ Error con subtítulos automáticos {lang}: {e}")
                            continue
            
            if not sub_data:
                disponibles = list(subtitulos_manuales.keys()) + list(subtitulos_auto.keys())
                return jsonify({
                    'exito': False,
                    'error': 'No se encontraron subtítulos en español',
                    'video_id': video_id,
                    'idiomas_disponibles': disponibles
                }), 404
            
            print(f"📄 Datos de subtítulos descargados: {len(sub_data)} bytes")
            
            # Parsea el texto
            texto = None
            
            # Intenta JSON3
            if 'events' in sub_data or '"events"' in sub_data:
                texto = parsear_json3(sub_data)
            
            # Intenta XML/SRV3
            if not texto and ('<text' in sub_data or '<?xml' in sub_data):
                texto = parsear_srv3(sub_data)
            
            # Intenta VTT
            if not texto and 'WEBVTT' in sub_data:
                texto = parsear_vtt(sub_data)
            
            # Limpieza genérica
            if not texto:
                texto = limpiar_texto_subtitulos(sub_data)
            
            if not texto or len(texto) < 10:
                return jsonify({
                    'exito': False,
                    'error': 'Los subtítulos están vacíos o no se pudieron parsear',
                    'video_id': video_id,
                    'tipo': tipo,
                    'debug_tamaño': len(sub_data),
                    'debug_inicio': sub_data[:200] if sub_data else None
                }), 404
            
            print(f"✅ Transcripción obtenida ({tipo}, {idioma_usado}): {len(texto)} caracteres")
            
            return jsonify({
                'exito': True,
                'video_id': video_id,
                'transcripcion': texto,
                'total_caracteres': len(texto),
                'tipo_subtitulos': tipo,
                'idioma': idioma_usado
            })
        
    except Exception as error:
        print(f"❌ Error completo: {type(error).__name__}: {str(error)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'error': f'{type(error).__name__}: {str(error)}',
            'video_id': video_id
        }), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Servidor iniciando con yt-dlp...")
    print(f"📍 Puerto: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)