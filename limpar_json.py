import json

def limpar():
    arquivo = 'docs/editais.json'
    with open(arquivo, 'r', encoding='utf-8') as f:
        editais = json.load(f)
        
    limpos = []
    removidos = 0
    for e in editais:
        titulo = str(e.get('t', '')).lower()
        link = str(e.get('link', '')).lower()
        
        # Se tiver baita ou 2022 no titulo/link, ignora (não adiciona na lista nova)
        if 'baita' in titulo or 'baita' in link or '2022' in titulo or '2022' in link:
            removidos += 1
        else:
            limpos.append(e)
            
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(limpos, f, ensure_ascii=False, indent=1)
        
    print(f"✅ Limpeza concluída! {removidos} editais antigos removidos do JSON.")

if __name__ == "__main__":
    limpar()
