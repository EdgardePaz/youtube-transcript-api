import requests

url = "https://youtube-transcript3.p.rapidapi.com/api/transcript"
params = {"videoId": "8S0FDjFBj8o", "lang": "es"}  # videoId, no video_id
headers = {
    "X-RapidAPI-Host": "youtube-transcript3.p.rapidapi.com",
    "X-RapidAPI-Key": "4db8764539mshfca57004d418dd6p1f779ajsn94d62ab586d8"
}

response = requests.get(url, headers=headers, params=params)
print(f"Código de respuesta: {response.status_code}")
print(f"Primeros 500 caracteres: {response.text[:500]}")

# Si quieres ver toda la respuesta
# print(f"Respuesta completa: {response.text}")