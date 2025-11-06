from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import re
import json

app = Flask(__name__)
CORS(app)

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
            
            subtitulos_manuales = info.get('subtitles', {})
            subtitulos_auto = info.get('automatic_captions', {})
            
            texto = None
            tipo = None
            idioma_usado = None
            formato_usado = None
            
            # Busca variantes de español
            idiomas_espanol = ['es', 'es-ES', 'es-MX', 'es-419', 'es-US']
            
            # Intenta manuales primero
            sub_list = None
            for lang in idiomas_espanol:
                if lang in subtitulos_manuales:
                    sub_list = subtitulos_manuales[lang]
                    tipo = 'manual'
                    idioma_usado = lang
                    break
            
            # Si no hay manuales, intenta automáticos
            if not sub_list:
                for lang in idiomas_espanol:
                    if lang in subtitulos_auto:
                        sub_list = subtitulos_auto[lang]
                        tipo = 'automático'
                        idioma_usado = lang
                        break
            
            if not sub_list:
                disponibles = list(subtitulos_manuales.keys()) + list(subtitulos_auto.keys())
                return jsonify({
                    'exito': False,
                    'error': 'No se encontraron subtítulos en español',
                    'video_id': video_id,
                    'idiomas_disponibles': disponibles
                }), 404
            
            # Intenta diferentes formatos en orden de preferencia
            formatos_preferencia = ['json3', 'srv3', 'vtt', 'ttml']
            sub_url = None
            
            for formato in formatos_preferencia:
                for sub_formato in sub_list:
                    if sub_formato.get('ext') == formato:
                        sub_url = sub_formato['url']
                        formato_usado = formato
                        break
                if sub_url:
                    break
            
            # Si no encontró formato específico, usa el primero disponible
            if not sub_url and sub_list:
                sub_url = sub_list[0]['url']
                formato_usado = sub_list[0].get('ext', 'desconocido')
            
                                    # Descarga subtítulos con headers apropiados
            import urllib.request
            print(f"📥 Descargando subtítulos formato: {formato_usado}")
            print(f"🔗 URL: {sub_url[:100]}...")
            
            # Añade headers para simular navegador
            req = urllib.request.Request(
                sub_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': '*/*',
                    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                    'Referer': 'https://www.youtube.com/'
                }
            )
            
            try:
                response = urllib.request.urlopen(req, timeout=30)
                sub_data = response.read().decode('utf-8')
            except Exception as download_error:
                print(f"❌ Error descargando: {download_error}")
                # Intenta con requests como alternativa
                try:
                    import requests
                    response = requests.get(sub_url, timeout=30)
                    sub_data = response.text
                except:
                    return jsonify({
                        'exito': False,
                        'error': f'No se pudieron descargar los subtítulos: {str(download_error)}',
                        'video_id': video_id
                    }), 500
            
            # Intenta parsear según el formato
            if formato_usado == 'json3':
                texto = parsear_json3(sub_data)
                if texto:
                    print(f"✅ JSON3 parseado: {len(texto)} caracteres")
            
            if not texto and (formato_usado == 'srv3' or formato_usado == 'ttml'):
                texto = parsear_srv3(sub_data)
                if texto:
                    print(f"✅ SRV3/TTML parseado: {len(texto)} caracteres")
            
            if not texto and formato_usado == 'vtt':
                texto = parsear_vtt(sub_data)
                if texto:
                    print(f"✅ VTT parseado: {len(texto)} caracteres")
            
            # Si no funcionó ningún parser específico, limpia genéricamente
            if not texto:
                print("⚠️ Usando limpieza genérica")
                texto = limpiar_texto_subtitulos(sub_data)
                if texto:
                    print(f"✅ Limpieza genérica: {len(texto)} caracteres")
            
            # Validación final
            if not texto or len(texto) < 10:
                print(f"❌ Texto final muy corto o vacío: '{texto[:100] if texto else 'None'}'")
                return jsonify({
                    'exito': False,
                    'error': 'Los subtítulos están vacíos o no se pudieron parsear',
                    'video_id': video_id,
                    'formato': formato_usado,
                    'debug_primeros_caracteres': sub_data[:500],
                    'debug_tamaño': len(sub_data)
                }), 404
            
            print(f"✅ Transcripción obtenida ({tipo}, {idioma_usado}, {formato_usado}): {len(texto)} caracteres")
            
            return jsonify({
                'exito': True,
                'video_id': video_id,
                'transcripcion': texto,
                'total_caracteres': len(texto),
                'tipo_subtitulos': tipo,
                'idioma': idioma_usado,
                'formato': formato_usado
            })
        
    except Exception as error:
        print(f"❌ Error: {type(error).__name__}: {str(error)}")
        import traceback
        print(traceback.format_exc())
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