# MNI-PJE

Este projeto contém um conjunto de utilitários para integração com o sistema Processo Judicial Eletrônico (PJe) através do Modelo Nacional de Interoperabilidade (MNI). 
O objetivo é facilitar a consulta de processos e avisos pendentes utilizando Python e bibliotecas como Zeep para conexão via SOAP.

## Funcionalidades

- **Consulta de processos**: Permite consultar processos em diferentes tribunais utilizando o protocolo SOAP.
- **Consulta de avisos pendentes**: Obtém avisos pendentes de um usuário no sistema PJe.
- **Consulta de teor de comunicação**: Recupera o teor das comunicações do processo.
- **Utilitários**: Funções auxiliares para formatação de dados e manipulação de XML.

## Exemplo
- [Google Colab](https://colab.research.google.com/drive/1BGbt3PV-qoUKp71dnvp0-uUN4-T8nT28#scrollTo=7WtQFs_urina).

## Requisitos

- Python 3.7+
- pandas
- requests
- zeep
- xmltodict

Você pode instalar as dependências necessárias utilizando o seguinte comando:

```bash
pip install pandas requests zeep xmltodict
