import requests

url = "https://notify.eskiz.uz/api/auth/login?"

payload={
    'email': 'fazliddinabdukhakimov@gmail.com',
    'password': 'NdjxlPM^Oagye$6@'
}

files=[

]
headers = {}

response = requests.post(url, headers=headers, data=payload, files=files)

print(response.text)


