"""Envio de fotos para o Supabase Storage.

O arquivo é enviado para um bucket e a função devolve a URL pública, que é
salva na coluna foto_url da tabela "integrantes" (e exibida em Quem Somos).

Configuração (arquivo .env, opcional):
    SUPABASE_BUCKET=fotos     # nome do bucket (padrão: "fotos"); precisa ser PÚBLICO
"""
import json
import os
import urllib.error
import urllib.request
import uuid

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB


class ErroUpload(Exception):
    """Erro de envio com mensagem já pronta para mostrar ao usuário."""


def _tipo_da_imagem(dados):
    """Descobre o tipo real pelo conteúdo do arquivo (não confia só na extensão)."""
    if dados[:3] == b'\xff\xd8\xff':
        return 'image/jpeg', 'jpg'
    if dados[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png', 'png'
    if dados[:4] == b'GIF8':
        return 'image/gif', 'gif'
    if dados[:4] == b'RIFF' and dados[8:12] == b'WEBP':
        return 'image/webp', 'webp'
    return None, None


def enviar_foto(arquivo):
    """Envia um UploadedFile do Django e devolve a URL pública da imagem."""
    url_base = (os.environ.get('SUPABASE_URL') or '').rstrip('/')
    chave = os.environ.get('SUPABASE_KEY') or ''
    bucket = os.environ.get('SUPABASE_BUCKET') or 'fotos'
    if not url_base or not chave:
        raise ErroUpload('Configure SUPABASE_URL e SUPABASE_KEY no arquivo .env.')

    if arquivo.size > TAMANHO_MAXIMO:
        raise ErroUpload('A imagem é muito grande. O tamanho máximo é 5 MB.')

    dados = arquivo.read()
    mime, extensao = _tipo_da_imagem(dados)
    if not mime:
        raise ErroUpload('Arquivo inválido. Envie uma imagem JPG, PNG, WEBP ou GIF.')

    caminho = f'integrantes/{uuid.uuid4().hex}.{extensao}'
    cabecalhos = {
        'apikey': chave,
        'Content-Type': mime,
        'Cache-Control': 'max-age=3600',
    }
    # Chaves antigas do Supabase são JWT e também vão em Authorization;
    # as chaves novas (sb_...) usam apenas o cabeçalho apikey.
    if chave.startswith('eyJ'):
        cabecalhos['Authorization'] = f'Bearer {chave}'

    requisicao = urllib.request.Request(
        f'{url_base}/storage/v1/object/{bucket}/{caminho}',
        data=dados, method='POST', headers=cabecalhos,
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=20):
            pass
    except urllib.error.HTTPError as e:
        try:
            detalhe = json.loads(e.read().decode('utf-8', 'replace'))
            detalhe = detalhe.get('message') or detalhe.get('error') or ''
        except Exception:
            detalhe = ''
        texto = detalhe.lower()
        if e.code == 404 or 'bucket not found' in texto:
            raise ErroUpload(f'O bucket "{bucket}" não existe no Supabase. Crie-o (público) em Storage.')
        if e.code in (400, 401, 403) and ('row-level' in texto or 'policy' in texto or 'unauthorized' in texto or e.code in (401, 403)):
            raise ErroUpload('O Supabase negou o envio (sem permissão no Storage). Crie a policy de INSERT para o bucket ou use a chave service_role no .env.')
        raise ErroUpload(f'Não foi possível enviar a imagem (erro {e.code}). {detalhe}'.strip())
    except urllib.error.URLError:
        raise ErroUpload('Não foi possível conectar ao Supabase. Verifique sua internet.')

    return f'{url_base}/storage/v1/object/public/{bucket}/{caminho}'
