# https://www.pje.jus.br/wiki/index.php/Utiliza%C3%A7%C3%A3o_do_PJe
# https://www.pje.jus.br/wiki/index.php/Tutorial_MNI
# https://docs.pje.jus.br/
# pje1g-integracao.tse.jus.br

# pandas para gerar a tabela de dados
import pandas as pd
# Só para organizar as datas
import datetime
# Caso tenha algum problema de SSL
from requests import Session
# biblioteca para gerar uma conexão com o protocolo SOAP que é o utilizado no MNI
try:
    from zeep.transports import Transport
    from zeep.plugins import HistoryPlugin
    import zeep
    from zeep.helpers import serialize_object
except:
    print('Por favor, instale a biblioteca zeep:\npip install zeep')

# Biblioteca para fazer requisições http
from requests.auth import HTTPBasicAuth
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from lxml import etree
from functools import reduce

try:
    import xmltodict
except:
    print('Por favor, instale a biblioteca xmltodict:\npip install xmltodict')

import traceback
disable_warnings(InsecureRequestWarning)

import warnings
warnings.filterwarnings('ignore')
# warnings.filterwarnings(action='once')

# === UTILIDADES
def remover_espacos_duplos(texto):
    '''Remove espaços duplos de uma string'''
    import re
    try:
        return " ".join(re.split(r"\s+", texto))
    except:
        return texto


def deep_get(dictionary, keys, default=''):
    '''Retorna o valor de um dicionário aninhado, caso não encontre retorna o valor default'''
    
    return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)


def extrair_informacao_do_xml_avisos(xml_str, retornar_df=True):
    '''Extrai informações do XML de avisos pendentes'''
    
    dicionario = xmltodict.parse(xml_str)
    dicionario = dict(dicionario)
    resultados = []

    cod = str(dicionario.get('soap:Envelope').get('soap:Body').keys())
    cod = cod[cod.find("'ns")+1:cod.find(":")]
    chave = f'{cod}:consultarAvisosPendentesResposta'

    #print('sucesso: ', dicionario.get('soap:Envelope').get('soap:Body').get(chave).get('sucesso'))
    #print('mensagem: ', dicionario.get('soap:Envelope').get('soap:Body').get(chave).get('mensagem'))
    #print('avisos: ', dicionario.get('soap:Envelope').get('soap:Body').get(chave).get('aviso'))
    avisos = dicionario.get('soap:Envelope').get('soap:Body').get(chave).get('aviso')

    for aviso in avisos:

        mapa = {}
        cod = list(aviso.keys())[-1]
        cod = cod[cod.find("'ns")+1:cod.find(":")]
        # print(cod)

        # print(aviso.keys())
        # ['@idAviso', '@tipoComunicacao', 'ns2:destinatario', 'ns2:processo', 'ns2:dataDisponibilizacao']
        mapa['Data-Expediente'] = formatar_data_sem_mascara(aviso.get(cod+':dataDisponibilizacao'))
        mapa['Destinatário'] = aviso.get(cod+':destinatario').get(cod+':pessoa').get('@nome')
        mapa['Origem'] = aviso.get(cod+':processo').get(cod+':orgaoJulgador').get('@nomeOrgao')
        mapa['Processo'] = aviso.get(cod+':processo').get('@numero')
        mapa['ID-Expediente'] = aviso.get('@idAviso')
        # mapa['Tipo-Expediente'] = aviso.get('@tipoComunicacao')
        resultados.append(mapa)

    if retornar_df is True:
        df = pd.DataFrame(resultados)
        if df.empty:
            return []
        else:
            # return df.sort_values(by=['Data-Expediente', 'Processo'])
            return df.sort_values(by='Data-Expediente', ascending=True)
    else:
        return resultados


def extrair_informacao_do_xml_consulta(xml_str, dev_mod=False):
    '''Extrai informações do XML de consulta de processo'''
    dicionario = xmltodict.parse(xml_str)
    dicionario = dict(dicionario)
    mapa = {}
    processo = ''

    # organizando dict
    cod = str(dicionario.get('soap:Envelope', {}).get('soap:Body', {}).keys())
    if cod:
        cod = cod[cod.find("'ns")+1:cod.find(":")]
        chave = f'{cod}:consultarProcessoResposta'
        processo = dicionario.get('soap:Envelope', {}).get('soap:Body', {}).get(chave, {}).get('processo', '')

    if processo == '':
        processo = deep_get(dicionario, "processo")

    if processo:
        cod = str(processo.keys())
        cod = cod[cod.find("'ns")+1:cod.find(":")]
    else:
        return {}

    if dev_mod is True:
        print(processo.keys())

    mapa['processo'] = deep_get(processo, f"{cod}:dadosBasicos.@numero")

    mapa['juizo'] = {}
    mapa['juizo']['local'] = deep_get(processo, f"{cod}:dadosBasicos.{cod}:orgaoJulgador.@nomeOrgao").upper()
    mapa['juizo']['ajuizado_em'] = formatar_data_sem_mascara(deep_get(processo, f"{cod}:dadosBasicos.@dataAjuizamento"))
    mapa['juizo']['valor'] = deep_get(processo, f"{cod}:dadosBasicos.{cod}:valorCausa")
    mapa['juizo']['status'] = deep_get(processo, f"{cod}:dadosBasicos.@valor", '')
    if mapa['juizo']['status'] == '':
        try:
            mapa['juizo']['status'] = deep_get(processo, f'{cod}:dadosBasicos.{cod}:outroParametro', {})[0].get('@valor', '')
        except KeyError:
            pass

    try:
        mapa['envolvidos'] = [ f"{item[cod+':parte'][cod+':pessoa']['@nome']}" for item in deep_get(processo, f"{cod}:dadosBasicos.{cod}:polo", []) ]
        mapa['envolvidos'] = ', '.join(mapa['envolvidos'][:4]).upper()
    except Exception as e:
        # print(e)
        mapa['envolvidos'] = ''

    mapa['pessoas'] = []
    polos = deep_get(processo, f"{cod}:dadosBasicos.{cod}:polo", [])
    lista_pessoas = []

    for polo in polos:

        if type(deep_get(polo, f"{cod}:parte")) is list:

            for parte in deep_get(polo, f"{cod}:parte", []):

                try:
                    pessoa = {}
                    pessoa['Nome'] = deep_get(parte, f'{cod}:pessoa.@nome')
                    pessoa['Documento'] = deep_get(parte, f'{cod}:pessoa.@numeroDocumentoPrincipal')
                    pessoa['Nascimento'] = deep_get(parte, f'{cod}:pessoa.@dataNascimento')
                    if pessoa.get('Nascimento') is None:
                        pessoa['Nascimento'] = deep_get(parte, f'{cod}:pessoa.{cod}:pessoaVinculada.@dataNascimento')

                    pessoa['CEP'] = deep_get(parte, f'{cod}:pessoa.{cod}:endereco.@cep')
                    pessoa['CIDADE'] = deep_get(parte, f'{cod}:pessoa.{cod}:endereco.{cod}:cidade')
                    pessoa['UF'] = deep_get(parte, f'{cod}:pessoa.{cod}:endereco.{cod}:estado')

                    pessoa['Advogados'] = deep_get(parte, f'{cod}:advogado')
                    if type(pessoa['Advogados']) is list:
                        pessoa['Advogados'] = '; '.join([ f"{deep_get(adv, '@nome')} - {deep_get(adv, '@inscricao', '')}" for adv in pessoa['Advogados'] ])
                    else:
                        pessoa['Advogados'] = f"{deep_get(pessoa['Advogados'], '@nome')} - {deep_get(pessoa['Advogados'], '@inscricao', '')}"

                    if pessoa.get('Nascimento'):
                        pessoa['Nascimento'] = datetime.datetime.strptime(pessoa.get('Nascimento'), '%Y%m%d').strftime('%d/%m/%Y')

                    lista_pessoas.append(pessoa)
                    if len(lista_pessoas) > 10:
                        break

                except Exception as e:
                    # print(e)
                    continue
        else:
            parte = deep_get(polo, f"{cod}:parte")
            pessoa = {}
            pessoa['Nome'] = deep_get(parte, f'{cod}:pessoa.@nome')
            pessoa['Documento'] = deep_get(parte, f'{cod}:pessoa.@numeroDocumentoPrincipal')
            pessoa['Nascimento'] = deep_get(parte, f'{cod}:pessoa.@dataNascimento')
            if pessoa.get('Nascimento') is None:
                pessoa['Nascimento'] = deep_get(parte, f'{cod}:pessoa.{cod}:pessoaVinculada.@dataNascimento')

            pessoa['CEP'] = deep_get(parte, f'{cod}:pessoa.{cod}:endereco.@cep')
            pessoa['CIDADE'] = deep_get(parte, f'{cod}:pessoa.{cod}:endereco.{cod}:cidade')
            pessoa['UF'] = deep_get(parte, f'{cod}:pessoa.{cod}:endereco.{cod}:estado')

            pessoa['Advogados'] = deep_get(parte, f'{cod}:advogado')
            if type(pessoa['Advogados']) is list:
                pessoa['Advogados'] = '; '.join([ f"{deep_get(adv, '@nome')} - {deep_get(adv, '@inscricao', '')}" for adv in pessoa['Advogados'] ])
            else:
                pessoa['Advogados'] = f"{deep_get(pessoa['Advogados'], '@nome')} - {deep_get(pessoa['Advogados'], '@inscricao', '')}"

            if pessoa.get('Nascimento'):
                pessoa['Nascimento'] = datetime.datetime.strptime(pessoa.get('Nascimento'), '%Y%m%d').strftime('%d/%m/%Y')

            lista_pessoas.append(pessoa)
            if len(lista_pessoas) > 10:
                break

    mapa['pessoas'] = lista_pessoas
    if mapa['envolvidos'] == '':
        mapa['envolvidos'] = ', '.join([ p.get('Nome', '').upper() for p in lista_pessoas[:3] ])

    if len(lista_pessoas) > 3:
        mapa['envolvidos'] += ' e outros.'

    mapa['movimentos'] = []
    mapa['movimentos_html'] = ''
    mapa['ult_mov'] = None

    # processo.ns2:movimento
    movimentos = deep_get(processo, f"{cod}:movimento", [])
    if movimentos:

        if type(movimentos) is list:
            '''
            maior_data = []
            for item in movimentos:

                maior_data.append(item.get("@dataHora"))

                data = formatar_data_sem_mascara(item.get("@dataHora"))
                movi = deep_get(item, f"{cod}:movimentoNacional.{cod}:complemento")
                mapa['movimentos_html'] += f'<p>{data} | {movi}</p> '
                mapa['movimentos'].append(f'{data} | {movi}')
            mapa['ult_mov'] = formatar_data_sem_mascara(max(maior_data))
            '''
            lista_mov = [ (item.get("@dataHora", '0'), deep_get(item, f"{cod}:movimentoNacional.{cod}:complemento")) for item in movimentos ]
            df = pd.DataFrame(lista_mov)
            for index, row in df.sort_values(by=0, ascending=False).head(25).iterrows():
                if mapa['ult_mov'] is None:
                    mapa['ult_mov'] = formatar_data_sem_mascara(row[0])
                mapa['movimentos'].append(f'{formatar_data_sem_mascara(row[0])} | {row[1]}')
                # mapa['movimentos_html'] += f'<p>{formatar_data_sem_mascara(row[0])} | {row[1]}</p> '

        else:
                data = formatar_data_sem_mascara(movimentos.get("@dataHora"))
                movi = deep_get(movimentos, f"{cod}:movimentoNacional.{cod}:complemento")
                # mapa['movimentos_html'] += f'<p>{data} | {movi}</p> '
                mapa['movimentos'].append(f'{data} | {movi}')
                mapa['ult_mov'] = data
    else:
        # mapa['movimentos_html'] += '<p>Nenhuma movimentação nos últimos 12 meses.</p> '
        mapa['movimentos'].append('Nenhuma movimentação nos últimos 12 meses.')
        mapa['ult_mov'] = ''

    documentos = deep_get(processo, f"{cod}:documento", {})

    if documentos:

        mapa['documentos'] = []

        if type(documentos) is list:
            for i in documentos:

                try:
                    if i.get("ns2:documentoVinculado"):
                        anexos = ''
                        #anexos = [ f"{deep_get(anex, '@idDocumento')} - {deep_get(anex, '@descricao', '')}" for anex in i.get("ns2:documentoVinculado") ]
                        #anexos = '\n'.join(x for x in anexos if x.replace(' - ', ''))
                    else:
                        anexos = ''
                except:
                    anexos = ''

                mapa['documentos'].append({
                    'data' : formatar_data_sem_mascara(i.get("@dataHora")),
                    'iden' : f'{i.get("@idDocumento")} - {i.get("@descricao")}',
                    'anex' : anexos
                    })
        else:
            try:
                if documentos.get("ns2:documentoVinculado"):
                    anexos = ''
                    #anexos = f"{deep_get(mapa['documentos']['anex'], '@idDocumento')} - {deep_get(mapa['documentos']['anex'], '@descricao', '')}"
                else:
                    anexos = ''
            except:
                anexos = ''

            mapa['documentos'].append({
                    'data' : formatar_data_sem_mascara(documentos.get("@dataHora")),
                    'iden' : f'{documentos.get("@idDocumento")} - {documentos.get("@descricao")}',
                    'anex' : ''#documentos.get("ns2:documentoVinculado")
                    })

    else:
        mapa['documentos'] = []

    return mapa


def retornar_link_mni(tribunal, wsld=True):

    # https://www.legalwtech.com.br/api/pjes/
    LINKS_PJE = {
        "TJES-1G": "https://pje.tjes.jus.br/pje/login.seam",
        "TJES-2G": "https://pje.tjes.jus.br/pje2g/login.seam",
        "TJPI-1G": "https://pje.tjpi.jus.br/1g/login.seam",
        "TJPI-2G": "https://pje.tjpi.jus.br/2g/login.seam",
        "TJRJ-1G": "https://tjrj.pje.jus.br/1g/login.seam",
        "TJRJ-2G": "https://tjrj.pje.jus.br/2g/login.seam",
        "TJRN-1G": "https://pje1g.tjrn.jus.br/pje/login.seam",
        "TJRN-2G": "https://pje2g.tjrn.jus.br/pje/login.seam"
    }	
    try:
        if wsld is True:
            return LINKS_PJE[tribunal].replace('login.seam', 'intercomunicacao?wsdl')
        else:
            return LINKS_PJE[tribunal]
    except:
        return ''


def formatar_data_sem_mascara(date_time_str=None, formato_origem='%Y%m%d%H%M%S', formato_final='%d/%m/%Y - %H:%M:%S'):

    try:
        if date_time_str:
            date_time_obj = datetime.datetime.strptime(date_time_str, formato_origem)
            return date_time_obj.strftime(formato_final)
        else:
            return None
    except Exception as e:
        print(f'ERRO / formatar_data_sem_mascara: {e}')
        return None


def traduzir_movimentos(dados_movimentos, formatar_html=True, quantidade=8):

    movimentos = list()

    try:
        data_ultimo_mov = formatar_data_sem_mascara(max(dados_movimentos['dataHora']))
    except:
        data_ultimo_mov = 'Não foi identificado movimentação nos últimos meses.'

    try:
        for index, row in dados_movimentos.sort_values(by='dataHora', ascending=False).head(quantidade).iterrows():

            try:
                movimento = dict(row["movimentoNacional"])
                movimento = movimento['complemento'][0]
                data = formatar_data_sem_mascara(row["dataHora"])
                movimento = (data, movimento) # f'{data} - {movimento}'

                movimentos.append(movimento)
            except Exception as e:
                print(f'ERRO / traduzir_movimentos: {e}')
                continue
    except KeyError:
        return '', ''

    if formatar_html is True:

        movimentos = [ f'<p>{item[0]} | {item[1]}</p>' for item in movimentos ]
        return ' '.join(movimentos), data_ultimo_mov

    return movimentos, data_ultimo_mov


def envolvidos(dados_participantes, formatar_html=True):

    try:
        lista_pessoas = list(set([item[1].upper() for item in list(dados_participantes['nome'].items())]))
        if formatar_html is True:
            return ', '.join(lista_pessoas)
        else:
            return lista_pessoas

    except Exception as e:
        print(f'ERRO / envolvidos: {e}')
        return []


def juizo(dados_basicos_processo):

    try:
        juizo = {
        'local' : dados_basicos_processo.loc[0, 'nomeOrgao'].upper(),
        'status' : dados_basicos_processo.loc[0, 'valor'].upper(),
        'ajuizado_em' : formatar_data_sem_mascara(dados_basicos_processo.loc[0, 'dataAjuizamento'].upper()),
        }
        return juizo
        #
    except Exception as e:
        print(f'ERRO / juizo: {e}')
        return ''


def explode_coluna(df, coluna, e_lista=False):

    try:
        if e_lista:
            df[coluna] = df[coluna].apply(lambda x: x[0])
        new = pd.DataFrame.from_records(df.pop(coluna).apply(lambda x: {} if pd.isna(x) else x))
        new = pd.concat([df, new], 1)
        return new
    except:
        pass
        # traceback.print_exc()

# link_pje é o link do mni normalmente vai ser do pje com /intercomunicacao?wsdl no final
# id_pje é o login do pje cpf/cnpj
# pass_pje é a senha do pje
# numero_processo é o número do processo que deseja consultar
# apartir_de_data é a data a partir do qual vai consultar documentos e movimentos, deve ser uma string no formato dia/mes/ano que a função já converte para o timestamp
# movimentos se deseja trazer os movimentos do processo
# documentos se deseja trazer os documentos do processo
# A função retorna verdadeiro caso a conexão seja um sucesso e retorna as quatro tabelas de informações na ordem básicos, participantes, movimentos e documentos
def consulta_processo_mni(
    num_processo_com_mascara,
    tribunal='TJES-1G',
    wsdl=None,
    id_pje=None,
    pass_pje=None,
    apartir_de_data="",
    participantes=True,
    movimentos=True,
    cabecalho=True,
    documentos=False,
    modo_dev=False,
    timeout=20,
    retornar_xml=False
    ):

    try:
        '''
        Caso tenha problemas de ssl
        '''
        session = Session()
        session.verify = False

        mapa = {}
        if not id_pje or not pass_pje:
            return 
        if not wsdl:
            wsdl = retornar_link_mni(tribunal)

        if num_processo_com_mascara.find('.') != -1:
            num_processo_com_mascara = num_processo_com_mascara.replace('-', '').replace('.', '')

        session.auth = HTTPBasicAuth(id_pje, pass_pje)
        session.headers = {"Content-Type": "text/xml;charset=UTF-8"}

        transport = Transport(session=session, timeout=timeout)
        # cria uma conexão com o protocolo soap
        # Caso tenha problema de ssl transport=transport
        settings = zeep.Settings(strict=False, xml_huge_tree=True)
        history = HistoryPlugin()
        client = zeep.Client(wsdl=wsdl, transport=transport, settings=settings, plugins=[history])

        if apartir_de_data != '':
            apartir_de_data = datetime.datetime.strptime(apartir_de_data, "%d/%m/%Y")

        # utiliza a função do soap
        resp = client.service.consultarProcesso(
            idConsultante=id_pje,
            senhaConsultante=pass_pje,
            numeroProcesso=num_processo_com_mascara,
            dataReferencia=apartir_de_data,
            movimentos=movimentos,
            incluirCabecalho=cabecalho,
            incluirDocumentos=documentos
        )

        pretty_xml = etree.tostring(history.last_received["envelope"], encoding="unicode", pretty_print=True)

        if retornar_xml is True:
            resultado = {
            'xml': remover_espacos_duplos(pretty_xml)
            }
            return resultado
        # print(pretty_xml)

        # Caso a conexão seja um sucesso
        if resp['sucesso'] is True:

            if modo_dev is True:
                print('Sucesso')

            mapa = extrair_informacao_do_xml_consulta(pretty_xml)
            mensagem = str(resp['mensagem'])

            # Seleciona a parte de dados básicos
            resp_ = resp['processo']['dadosBasicos']

            try:
                series_basicos = pd.Series(serialize_object(resp_)).drop('polo')
                series_basicos = pd.DataFrame(series_basicos).transpose()
                series_basicos = explode_coluna(series_basicos, 'assunto', True)
                # series_basicos = explode_coluna(series_basicos, 'assunto', True)
                # 'NoneType' object is not subscriptable
                series_basicos = explode_coluna(series_basicos, 'outroParametro', True)
                series_basicos = explode_coluna(series_basicos, 'orgaoJulgador')

                # Seleciona os participantes
                if participantes is True:
                    resp_ = resp['processo']['dadosBasicos']['polo']
                    df_participantes = pd.DataFrame(serialize_object(resp_))
                    if len(df_participantes)> 0:
                        df_participantes = explode_coluna(df_participantes, 'parte', True)
                        df_participantes = explode_coluna(df_participantes, 'pessoa')
                else:
                    df_participantes = None

                # Seleciona os movimentos
                if movimentos is True:
                    resp_ = resp['processo']['movimento']
                    df_movimentos = pd.DataFrame(serialize_object(resp_))
                    if len(df_movimentos)> 0:
                        df_movimentos = explode_coluna(df_movimentos, 'movimentoLocal')
                else:
                    df_movimentos = None
                # Seleciona os documentos
                if documentos is True:
                    resp_ = resp['processo']['documento']
                    df_documentos = pd.DataFrame(serialize_object(resp_))
                    if len(df_documentos)> 0:
                        df_documentos = explode_coluna(df_documentos, 'assinatura', True)
                else:
                    df_documentos = None

                resultado = {
                    'sucesso': True,
                    'series_basicos': series_basicos,
                    'df_participantes': df_participantes,
                    'df_movimentos': df_movimentos,
                    'df_documentos': df_documentos,
                    'mensagem': mensagem,
                    'link_mni': wsdl,
                    'mapa': mapa,
                    'xml': remover_espacos_duplos(pretty_xml)
                }

                return resultado

            except:
                resultado = {
                    'sucesso': True,
                    'mapa': mapa,
                    'mensagem': mensagem,
                    'link_mni': wsdl,
                    'xml': remover_espacos_duplos(pretty_xml)
                    }
                return resultado

        else:
            # print('Falhou')
            # with open('mni_falhou.txt', 'w') as arq:
                # arq.write(str(resp))
            if modo_dev is True:
                print(f'Falha: {resp}')

            resultado = {
                'sucesso': False,
                'series_basicos': '',
                'df_participantes': '',
                'df_movimentos': '',
                'df_documentos': '',
                'mensagem': str(resp['mensagem']),
                'link_mni': wsdl,
                'xml': pretty_xml
            }

            return resultado

    except Exception as e:
        if modo_dev is True:
            print(f'Falha: {e}')
            traceback.print_exc()

        resultado = {
            'sucesso': None,
            'series_basicos': '',
            'df_participantes': '',
            'df_movimentos': '',
            'df_documentos': '',
            'mensagem': e,
            'link_mni': wsdl,
        }

        return resultado


def consulta_avisos_pendentes_mni(
    link_pje=None,
    id_pje=None,
    pass_pje=None,
    apartir_de_data="",
    tipo_pendencia=None,
    modo_dev=False,
    timeout=20,
    ):

    try:
        session = Session()
        session.verify = False

        if id_pje is None:
            return {'sucesso': False, 'mensagem': 'ID não informado.'}
        if pass_pje is None:
            return {'sucesso': False, 'mensagem': 'Senha não informada.'}

        session.auth = HTTPBasicAuth(id_pje, pass_pje)

        transport = Transport(session=session, timeout=timeout)
        settings = zeep.Settings(strict=False, xml_huge_tree=True)
        history = HistoryPlugin()
        client = zeep.Client(wsdl=link_pje, transport=transport, settings=settings, plugins=[history])

        if apartir_de_data != '':
            # Transforma a string de data em timestamp
            apartir_de_data = datetime.datetime.strptime(apartir_de_data, "%d/%m/%Y")

        # utiliza a função do soap
        resp = client.service.consultarAvisosPendentes(
            idConsultante=id_pje,
            senhaConsultante=pass_pje,
            dataReferencia=apartir_de_data,
            # tipoPendencia=tipo_pendencia,
            )

        pretty_xml = etree.tostring(history.last_received["envelope"], encoding="unicode", pretty_print=True)

        #if modo_dev is True:
            #print(pretty_xml)

        # Caso a conexão seja um sucesso
        if resp['sucesso'] is True:

            if modo_dev is True:
                print('Sucesso')
                # não existe mais
                # recibo = str(resp['recibo'])

            mensagem = str(resp['mensagem'])
            # avisos = serialize_object(resp['aviso'])
            try:
                avisos = extrair_informacao_do_xml_avisos(pretty_xml, retornar_df=True)
            except Exception as e:
                if modo_dev is True:
                    print(f'Falha: {e}')
                    traceback.print_exc()
                avisos = []

            resultado = {
                'sucesso': True,
                'mensagem': mensagem,
                'avisos': avisos,
            }

            return resultado

        else:
            # print('Falhou')
            # with open('mni_falhou.txt', 'w') as arq:
                # arq.write(str(resp))
            if modo_dev is True:
                print(f'Falha: {resp}')

            resultado = {
                'sucesso': False,
                'mensagem': str(resp['mensagem']),
                'avisos': [],
            }

            return resultado

    except Exception as e:
        if modo_dev is True:
            print(f'Falha: {e}')
            traceback.print_exc()

        resultado = {
            'sucesso': None,
            'mensagem': e,
            'avisos': []
        }

        return resultado


def consulta_teor_mni(
    link_pje=None,
    id_pje=None,
    pass_pje=None,
    numero_processo=None,
    id_documento=None,
    modo_dev=False,
    timeout=20,
    ):

    if not id_pje or not pass_pje:
        return {'sucesso': False, 'mensagem': 'ID ou senha não informados.'}

    try:
    
        session = Session()
        session.verify = False

        session.auth = HTTPBasicAuth(id_pje, pass_pje)
        ### ngs

        transport = Transport(session=session, timeout=timeout)
        # +'/pje/intercomunicacao?wsdl'
        wsdl = link_pje
        # cria uma conexão com o protocolo soap
        # Caso tenha problema de ssl transport=transport

        settings = zeep.Settings(strict=False, xml_huge_tree=True)
        client = zeep.Client(wsdl=wsdl, transport=transport, settings=settings)

        # utiliza a função do soap
        resp = client.service.ConsultarTeorComunicacao(
            idConsultante=id_pje,
            senhaConsultante=pass_pje,
            numeroProcesso=numero_processo,
            identificadorAviso=id_documento,
            )

        if modo_dev is True:
            print(resp)

        # Caso a conexão seja um sucesso
        if resp['sucesso'] is True:

            if modo_dev is True:
                print('Sucesso')

            mensagem = str(resp['mensagem'])

            resultado = {
                'sucesso': True,
                'mensagem': mensagem,
                'comunicacao': serialize_object(resp)
            }

            return resultado

        else:
            if modo_dev is True:
                print(f'Falha: {resp}')

            resultado = {
                'sucesso': False,
                'mensagem': str(resp['mensagem']),
            }

            return resultado

    except Exception as e:
        if modo_dev is True:
            print(f'Falha: {e}')
            traceback.print_exc()

        resultado = {
            'sucesso': None,
            'mensagem': e,
        }

        return resultado


def consultar_processo(
    ordem=dict(), retornar_df=False, data_ref='01/03/2022', 
    documentos=False, timeout=25, modo_dev=False, retornar_xml=False
):

    if not ordem:
        return None

    resultado = consulta_processo_mni(
        num_processo_com_mascara=ordem.get('processo'),
        link_pje=ordem.get('link'),
        id_pje=ordem.get('usuario'),
        pass_pje=ordem.get('senha'),
        apartir_de_data=data_ref,
        participantes=True,
        movimentos=True,
        cabecalho=True,
        documentos=documentos,
        modo_dev=modo_dev,
        processo_grau=ordem.get('grau'),
        timeout=timeout,
        retornar_xml=retornar_xml
        )

    if retornar_xml is True:
        return resultado

    if resultado.get('sucesso') is True:

        if resultado.get('mapa'):

            retorno = {
                'sucesso': True,
                'envolvidos': resultado['mapa']['envolvidos'],
                'movimentos': resultado['mapa']['movimentos_html'],
                'ult_mov': resultado['mapa'].get('ult_mov', ''),
                'juizo': resultado['mapa']['juizo'],
                'mensagem': 'Sucesso ao consultar.',
                'link_mni': resultado.get('link_mni'),
                'xml': resultado.get('xml'),
                'mapa': resultado.get('mapa', {})
                }
            return retorno

        if retornar_df is True:

            if modo_dev is True:
                resultado['series_basicos'].to_excel('dados_basicos.xlsx', index=False)
                resultado['df_participantes'].to_excel('dados_participantes.xlsx', index=False)
                resultado['df_movimentos'].to_excel('dados_movimentos.xlsx', index=False)
                resultado['df_documentos'].to_excel('dados_documentos.xlsx', index=False)

            return resultado
            # resultado['dados_basicos_processo'], resultado['dados_participantes'], resultado['dados_movimentos'], resultado['dados_documentos']

        movimentos = traduzir_movimentos(resultado['df_movimentos'])

        retorno = {
            'sucesso': True,
            'envolvidos': envolvidos(resultado['df_participantes']),
            'movimentos': movimentos[0],
            'ult_mov': movimentos[1],
            'juizo': juizo(resultado['series_basicos']),
            'mensagem': 'Sucesso ao consultar.',
            'link_mni': resultado.get('link_mni'),
            'xml': resultado.get('xml')
            }
        return retorno

    else:
        resultado.update({'info': {'Processo inválido, não localizado ou com segredo de justiça.'}})
        return resultado


if __name__ == "__main__":

    '''
    r = consulta_avisos_pendentes_mni(
        link_pje='https://pje1g.tjrn.jus.br/pje/intercomunicacao?wsdl',
        id_pje='LOGIN',
        pass_pje='SENHA',
        apartir_de_data="",
        tipo_pendencia=None,
        modo_dev=False,
        )
    print(r)
    '''

    # 0807483-73.2024.8.19.0011 - TJRJ
    # 0824489-24.2024.8.18.0140 - TJPI
    print(
        consulta_processo_mni(
            '0802452-62.2023.8.18.0164', retornar_xml=False,
            id_pje='LOGIN', pass_pje='SENHA',
            tribunal='TJPI-1G', wsdl='https://pje.tjpi.jus.br/1g/intercomunicacao?wsdl',
        ),
    )
