import requests
import time

f = open("DNS.txt", 'r')
dns = f.readline()
f.close()

usuario = str(input("Escolha o que fazer: Get (G), Post (P), Delete(D), Teste (any): \n"))


if(usuario == "G"):
    r = requests.get(f"http://{dns}:80/tasks/api/tasks")
    print(r.text)
elif(usuario == "P"):
    titulo = str(input("Insira um titulo: \n"))
    descricao = str(input("Insira uma descricao: \n"))
    r2 = requests.post(f"http://{dns}:80/tasks/api/tasks", json={"title": titulo, "description": descricao})
    print(r2.text)
elif(usuario == "D"):
    r3 = requests.delete(f"http://{dns}:80/tasks/api/tasks")
    print(r3.text)
else:
    while(True):
        print("testando AG")
        r = requests.get(f"http://{dns}:80/tasks/api/tasks")
        print(r.text)
        time.sleep(1)