import requests
from bs4 import BeautifulSoup as BS
import re

TAG_RE = re.compile(r'<[^>]+>')

def remove_tags(text):
    return TAG_RE.sub('', text)

links = ["https://uspdigital.usp.br/jupiterweb/jupDisciplinaLista?codcg=55&letra=A-Z&tipo=D","https://uspdigital.usp.br/jupiterweb/jupDisciplinaLista?codcg=18&letra=A-Z&tipo=D","https://uspdigital.usp.br/jupiterweb/jupDisciplinaLista?codcg=76&letra=A-Z&tipo=D","https://uspdigital.usp.br/jupiterweb/jupDisciplinaLista?codcg=75&letra=A-Z&tipo=D","https://uspdigital.usp.br/jupiterweb/jupDisciplinaLista?codcg=99&letra=A-Z&tipo=D"]


for l in links:
	r = requests.get(l)
	disciplinas = []
	codigos_ja_consultados = []
	if(r.status_code == requests.codes.ok):
		content = r.text
		soup = BS(content,"html.parser")
		linhas = soup.find_all("tr")
		for linha in linhas:
			colunas = linha.find_all("td")
			codigo_disciplina = 	colunas[0].text
			codigo_disciplina = codigo_disciplina.strip()
			if(len(codigo_disciplina)<10 and ('1' in codigo_disciplina or '0' in codigo_disciplina or '2' in codigo_disciplina) and codigo_disciplina not in codigos_ja_consultados):

				r1 = requests.get("https://uspdigital.usp.br/jupiterweb/obterTurma?sgldis="+codigo_disciplina).text
				r2 = requests.get("https://uspdigital.usp.br/jupiterweb/listarCursosRequisitos?coddis="+codigo_disciplina).text

				soup = BS(r1,"html.parser")
				horarios = []
				for tr in soup.find_all("tr",{"valign":"top","class":"txt_verdana_8pt_gray"}):
					linha = [x.getText() for x in tr.find_all("span",{"class":"txt_arial_8pt_gray"})]
					if(len(linha)>3):
						horarios.append(" ".join(linha))


				if("Não existe oferecimento para a sigla" not in r1 and "A sigla da disciplina deve ter"):
					nome_disciplina = 	colunas[1].text
					nome_disciplina = nome_disciplina.strip()
					if("Disciplina não tem requisitos" in r2):
						print(codigo_disciplina,nome_disciplina,"(SEM REQUISITO)","HORARIOS: "+str(";".join(horarios)))	

					else:
						soup = BS(r2,"html.parser")
						linhas = soup.find_all("tr",{"valign":"top", "bgcolor":"#FFFFFF","class":"txt_verdana_8pt_gray"})
						disciplinas = []
						for l in linhas:
							linha = l.find("td",{"colspan":"2"}).getText()
							linha = remove_tags(linha)
							linha = ' '.join(linha.split())
							if(linha not in disciplinas):
								disciplinas.append(linha)
						print(codigo_disciplina,nome_disciplina,"(COM REQUISITO) ->",";".join(disciplinas),"HORARIOS: "+str(";".join(horarios)))
					codigos_ja_consultados.append(codigo_disciplina)