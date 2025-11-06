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
        
        for event in json_data.get('events', []):
            if 'segs' in event:
                for seg in event['segs']:
                    if 'utf8' in seg:
                        textos.append(seg['utf8'])
        
        return ' '.join(textos)
    except:
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
            
            # Descarga subtítulos
            import urllib.request
            print(f"📥 Descargando subtítulos formato: {formato_usado}")
            response = urllib.request.urlopen(sub_url)
            sub_data = response.read().decode('utf-8')
            
            # Intenta parsear según el formato
            if formato_usado == 'json3':
                texto = parsear_json3(sub_data)
            elif formato_usado == 'srv3' or formato_usado == 'ttml':
                texto = parsear_srv3(sub_data)
            elif formato_usado == 'vtt':
                texto = parsear_vtt(sub_data)
            
            # Si no funcionó ningún parser específico, limpia genéricamente
            if not texto:
                print("⚠️ Usando limpieza genérica")
                texto = limpiar_texto_subtitulos(sub_data)
            
            if not texto or len(texto) < 10:
                return jsonify({
                    'exito': False,
                    'error': 'Los subtítulos están vacíos o no se pudieron parsear',
                    'video_id': video_id,
                    'formato': formato_usado
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