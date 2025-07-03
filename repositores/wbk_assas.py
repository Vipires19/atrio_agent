import requests
import os

### DOCUMENTAÇÃO API ASSAS - https://docs.asaas.com/  ###

class Webhook():
    def __init__(self):
        super().__init__()

    def create_webhook(self,name, access_token):    
        url = "https://sandbox.asaas.com/api/v3/webhook" #O Sandbox do assas é para desenvolvimento, para produção a url muda para https://api.asaas.com/

        payload = { "name": name,
                    "sendType": "SEQUENTIALLY",
                    "url": "SEU DOMÍNIO AQUI",
                    "email": "SEU EMAIL AQUI",
                    "enabled" : True,
                    "interrupted": False,
                    "apiVersion": 3,
                    "events": [ "LISTA DE EVENTOS QUE SERÃO ACEITOS NO WEBHOOK. VERIFICAR DOCUMENTAÇÃO" ]}
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "access_token": access_token
        }

        response = requests.post(url, json=payload, headers=headers)

        print(response.text)
