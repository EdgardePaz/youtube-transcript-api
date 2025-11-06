from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import re

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

# NUEVO: Endpoint para verificar qué idiomas tiene un video
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
                'tiene_espanol_manual': 'es' in subtitulos_manuales or any('es' in s for s in subtitulos_manuales),
                'tiene_espanol_auto': 'es' in subtitulos_auto or any('es' in s for s in subtitulos_auto)
            })
    
    except Exception as error:
        return jsonify({'error': str(error)}), 500

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
            
            # Busca variantes de español
            idiomas_espanol = ['es', 'es-ES', 'es-MX', 'es-419', 'es-US']
            
            # Intenta manuales primero
            for lang in idiomas_espanol:
                if lang in subtitulos_manuales:
                    sub_list = subtitulos_manuales[lang]
                    tipo = 'manual'
                    idioma_usado = lang
                    break
            
            # Si no hay manuales, intenta automáticos
            if not tipo:
                for lang in idiomas_espanol:
                    if lang in subtitulos_auto:
                        sub_list = subtitulos_auto[lang]
                        tipo = 'automático'
                        idioma_usado = lang
                        break
            
            if not tipo:
                # Muestra qué idiomas SÍ están disponibles
                disponibles = list(subtitulos_manuales.keys()) + list(subtitulos_auto.keys())
                return jsonify({
                    'exito': False,
                    'error': 'No se encontraron subtítulos en español',
                    'video_id': video_id,
                    'idiomas_disponibles': disponibles,
                    'sugerencia': 'Usa /check?video_id=XXX para ver idiomas disponibles'
                }), 404
            
            # Busca formato json3
            sub_url = None
            for formato in sub_list:
                if formato.get('ext') == 'json3':
                    sub_url = formato['url']
                    break
            
            if not sub_url and sub_list:
                sub_url = sub_list[0]['url']
            
            # Descarga subtítulos
            import urllib.request
            response = urllib.request.urlopen(sub_url)
            sub_data = response.read().decode('utf-8')
            
            # Parsea según el formato
            if 'json3' in sub_url or '"events"' in sub_data:
                # Formato JSON
                import json
                data = json.loads(sub_data)
                textos = []
                for event in data.get('events', []):
                    if 'segs' in event:
                        for seg in event['segs']:
                            if 'utf8' in seg:
                                textos.append(seg['utf8'])
                texto = ' '.join(textos)
            else:
                # Formato XML/VTT
                texto = re.sub(r'<[^>]+>', '', sub_data)
                texto = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}.*?\d{2}:\d{2}:\d{2}\.\d{3}', '', texto)
            
            # Limpia el texto
            texto = re.sub(r'\n+', ' ', texto)
            texto = re.sub(r'\s+', ' ', texto)
            texto = texto.strip()
            
            if not texto:
                return jsonify({
                    'exito': False,
                    'error': 'Los subtítulos están vacíos',
                    'video_id': video_id
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
        print(f"❌ Error: {type(error).__name__}: {str(error)}")
        return jsonify({
            'exito': False,
            'error': f'{type(error).__name__}: {str(error)}',
            'video_id': video_id
        }), 500

if __name__ == '__main__':
    print("🚀 Servidor iniciando con yt-dlp...")
    print("📍 Abre: http://localhost:5000")
    print("🔍 Verifica idiomas: http://localhost:5000/check?video_id=XXX")
    app.run(host='0.0.0.0', port=5000, debug=True)