import os,requests
r=requests.post(os.getenv('PUFFX_URL','http://127.0.0.1:8000')+'/v1/chat/completions',headers={'Authorization':'Bearer '+os.environ['PUFFX_API_KEY']},json={'messages':[{'role':'user','content':'Hello'}]});r.raise_for_status();print(r.json()['choices'][0]['message']['content'])
