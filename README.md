# usp-scheduler-search

Esse foi um script que eu construí anos atrás, enquanto estava na USP, para me auxiliar na escolha das disciplinas de cada semestre. 

Na prática é um scrapper que consulta o Júpiter (um sistema específico da USP para gerenciar a matricula dos alunos) e retorna um conjunto de entidades com APIs bastante convenientes para quem gosta de análise de dados. 

Com esse projeto e algumas funções auxiliares simples, várias perguntas interessantes podem ser respondidas, como por exemplo: 

#### Dada as disciplinas atualmente ofertadas:
* quais disciplinas o professor X vai lecionar esse semestre?
* qual é o máximo de disciplinas que consigo cursar nesse semestre?
* qual é o máximo de disciplinas que consigo cursar nesse semestre **deixando as quintas-feiras livre**?
* qual é o máximo de disciplinas que consigo cursar nesse semestre **sem aulas depois após 21:00**?
* (...)
	 
Após a imposição das restrições desejadas, a geração das grades possíveis é trivial. 
