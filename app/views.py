import json
import urllib.request
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .forms import FormServico
from .models import Servico, Categoria, Pedido
from .serializers import CategoriaSerializer
from .supabase_client import supabase
from .supabase_storage import enviar_foto, ErroUpload

# API externa (FakeStore) usada para compor o catálogo da página de Produtos (exigência do PDF)
API_PRODUTOS_EXTERNOS = "https://fakestoreapi.com/products"


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------
@login_required
def relatorios(request):

    servicos = Servico.objects.all()
    servicos_ativos = servicos.filter(ativo=True).count()
    servicos_inativos = servicos.filter(ativo=False).count()

    categorias = (
        servicos.values('categoria__nome')
        .annotate(quantidade=Count('id'))
        .order_by('categoria__nome')
    )

    return render(request, 'relatorio.html', {
        'total_servicos': servicos_ativos + servicos_inativos,
        'servicos_ativos': servicos_ativos,
        'servicos_inativos': servicos_inativos,
        'categorias_labels': [
            item['categoria__nome'] or 'Sem categoria'
            for item in categorias
        ],
        'categorias_valores': [
            item['quantidade']
            for item in categorias
        ],
        # Dados do gráfico de rosca (antes o template os pedia, mas a view não enviava)
        'status_labels': ['Ativos', 'Inativos'],
        'status_valores': [servicos_ativos, servicos_inativos],
    })


# ---------------------------------------------------------------------------
# API REST de categorias
# ---------------------------------------------------------------------------
@api_view(['GET', 'POST'])
def categoriasAPI(request):

    if request.method == 'GET':
        categorias = Categoria.objects.all()
        serializer = CategoriaSerializer(categorias, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = CategoriaSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'DELETE', 'PUT'])
def categoriaAPI(request, id_categoria):

    try:
        categoria = Categoria.objects.get(id=id_categoria)
    except Categoria.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = CategoriaSerializer(categoria)
        return Response(serializer.data)

    elif request.method == 'DELETE':
        categoria.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    elif request.method == 'PUT':
        serializer = CategoriaSerializer(categoria, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Páginas públicas
# ---------------------------------------------------------------------------
def index(request):
    return render(request, "index.html")


def quem_somos(request):
    """Página institucional; os integrantes vêm do banco remoto (Supabase)."""
    integrantes = []
    erro = False
    try:
        resposta = supabase.table("integrantes").select("*").order("id").execute()
        integrantes = resposta.data
    except Exception:
        erro = True
    return render(request, "quem_somos.html", {'integrantes': integrantes, 'erro': erro})


def _produtos_externos():
    """Busca os produtos da API externa. Guarda em cache por 10 min e nunca derruba a página."""
    produtos = cache.get('produtos_externos')
    if produtos is not None:
        return produtos, False
    try:
        requisicao = urllib.request.Request(
            API_PRODUTOS_EXTERNOS, headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(requisicao, timeout=6) as resp:
            produtos = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return [], True
    cache.set('produtos_externos', produtos, 600)
    return produtos, False


def produto(request):
    servicos = Servico.objects.filter(ativo=True)
    externos, erro_api = _produtos_externos()
    return render(request, 'produtos.html', {
        'servicos': servicos,
        'produtos_externos': externos,
        'erro_api': erro_api,
    })


# ---------------------------------------------------------------------------
# Pedidos (somente usuários logados)
# ---------------------------------------------------------------------------
@login_required
def comprar(request, id_servico):
    if request.method != 'POST':
        return redirect('produtos')

    servico = get_object_or_404(Servico, id=id_servico, ativo=True)
    Pedido.objects.create(
        usuario=request.user,
        servico=servico,
        nome_servico=servico.nome,
        preco=servico.preco,
    )
    messages.success(request, f'"{servico.nome}" foi adicionado aos seus pedidos.')
    return redirect('meus_pedidos')


@login_required
def meus_pedidos(request):
    pedidos = Pedido.objects.filter(usuario=request.user).select_related('servico')
    total = pedidos.aggregate(total=Sum('preco'))['total'] or 0
    return render(request, 'meus_pedidos.html', {'pedidos': pedidos, 'total': total})


@login_required
@require_POST
def remover_pedido(request, id_pedido):
    # Filtra por usuario: ninguém consegue remover o pedido de outra pessoa
    pedido = get_object_or_404(Pedido, id=id_pedido, usuario=request.user)
    nome = pedido.nome_servico
    pedido.delete()
    messages.success(request, f'O pedido "{nome}" foi removido.')
    return redirect('meus_pedidos')


# ---------------------------------------------------------------------------
# Gerenciamento de serviços (somente usuários logados)
# ---------------------------------------------------------------------------
def _url_filtros(params, **mudancas):
    """Monta a querystring mantendo os filtros atuais e trocando apenas o que mudou."""
    dados = {k: v for k, v in params.items() if v}
    dados.update(mudancas)
    dados = {k: v for k, v in dados.items() if v}
    return '?' + urlencode(dados) if dados else '?'


@login_required
def servicos(request):
    # Encadeia os filtros: ativo=True E preco diferente de 0
    servicos = Servico.objects.filter(ativo=True).exclude(preco=0)

    total_servicos = servicos.count()
    tem_servicos = servicos.exists()

    mais_barato = servicos.order_by('preco').first()
    mais_caro = servicos.order_by('-preco').first()

    busca = request.GET.get('busca')

    if busca:
        servicos = servicos.filter(nome__icontains=busca)
    categorias = Categoria.objects.filter(ativo=True)
    categoria = request.GET.get('categoria')

    if categoria and categoria.isdigit():
        servicos = servicos.filter(categoria_id=categoria)

    preco = request.GET.get('preco')

    if preco == 'baixo':
        servicos = servicos.filter(preco__lte=500)
    elif preco == 'medio':
        servicos = servicos.filter(preco__gte=500, preco__lte=1500)
    elif preco == 'alto':
        servicos = servicos.filter(preco__gt=1500)

    ordem = request.GET.get('ordem')

    if ordem == 'menor':
        servicos = servicos.order_by('preco')
    elif ordem == 'maior':
        servicos = servicos.order_by('-preco')
    elif ordem == 'nome':
        servicos = servicos.order_by('nome')
    else:
        servicos = servicos.order_by('nome')

    params = {'busca': busca, 'categoria': categoria, 'preco': preco, 'ordem': ordem}

    # Chips de filtro já com a URL pronta (os filtros se combinam entre si)
    chips_categoria = [
        {'nome': c.nome, 'url': _url_filtros(params, categoria=str(c.id)),
         'ativo': categoria == str(c.id)}
        for c in categorias
    ]
    chips_preco = [
        {'nome': nome, 'url': _url_filtros(params, preco=valor), 'ativo': preco == valor}
        for nome, valor in (('Até R$ 500', 'baixo'), ('R$ 500 - R$ 1.500', 'medio'),
                            ('Acima de R$ 1.500', 'alto'))
    ]
    chips_ordem = [
        {'nome': nome, 'url': _url_filtros(params, ordem=valor), 'ativo': ordem == valor}
        for nome, valor in (('Menor preço', 'menor'), ('Maior preço', 'maior'), ('Nome', 'nome'))
    ]

    contexto = {
        'servicos': servicos,
        'total_servicos': total_servicos,
        'tem_servicos': tem_servicos,
        'mais_barato': mais_barato,
        'mais_caro': mais_caro,
        'busca': busca,
        'categorias': categorias,
        'categoria': categoria,
        'preco': preco,
        'ordem': ordem,
        'chips_categoria': chips_categoria,
        'chips_preco': chips_preco,
        'chips_ordem': chips_ordem,
        'tem_filtro': any(params.values()),
    }

    return render(request, "servicos.html", contexto)


@login_required
def addServico(request):
    # "request.FILES or None": um dict de arquivos vazio (não None) faria o form
    # nascer "preenchido" e mostrar erros de validação já no primeiro acesso.
    form = FormServico(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço cadastrado com sucesso.')
            return redirect('servicos')

    return render(request, "add-servico.html", {'form': form})


@login_required
@require_POST
def delServico(request, id_servico):
    servico = get_object_or_404(Servico, id=id_servico)
    servico.delete()
    messages.success(request, 'Serviço excluído.')
    return redirect('servicos')


@login_required
def editServico(request, id_servico):
    servico = get_object_or_404(Servico, id=id_servico)
    form = FormServico(request.POST or None, request.FILES or None, instance=servico)

    if request.POST:
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço atualizado com sucesso.')
            return redirect('servicos')
    return render(request, "edit-servico.html", {'form': form, 'servico': servico})


# ---------------------------------------------------------------------------
# Equipe (Supabase) - somente usuários logados
# ---------------------------------------------------------------------------
@login_required
def integrantes(request):
    erro = False
    dados = []
    try:
        resposta = supabase.table("integrantes").select("*").order("id").execute()
        dados = resposta.data
    except Exception:
        erro = True
    return render(request, "integrantes.html", {'integrantes': dados, 'erro': erro})


SEM_ALTERACAO = object()  # nenhuma foto nova e nada para remover: mantém a foto atual


def _foto_do_formulario(request):
    """Decide o que fazer com foto_url a partir do formulário.

    - arquivo escolhido  -> envia ao Supabase Storage e devolve a URL pública
    - "Remover a foto"   -> devolve None (limpa a foto)
    - nada               -> devolve SEM_ALTERACAO (não mexe na foto atual)
    Levanta ErroUpload (com mensagem amigável) se o envio falhar.
    """
    arquivo = request.FILES.get("foto_arquivo")
    if arquivo:
        return enviar_foto(arquivo)
    if request.POST.get("remover_foto"):
        return None
    return SEM_ALTERACAO


@login_required
def addIntegrante(request):
    if request.method == "POST":
        dados = {
            "nome": request.POST.get("nome"),
            "cargo": request.POST.get("cargo"),
            "biografia": request.POST.get("biografia"),
        }
        try:
            foto = _foto_do_formulario(request)
            dados["foto_url"] = None if foto is SEM_ALTERACAO else foto
            resposta = supabase.table("integrantes").insert(dados).execute()
            if not resposta.data:
                raise ErroUpload('O Supabase não confirmou o cadastro (verifique a policy de INSERT da tabela integrantes).')
        except ErroUpload as erro:
            messages.error(request, str(erro))
            return render(request, "add-integrante.html", {'dados': request.POST})
        except Exception as erro:
            messages.error(request, f'Não foi possível salvar no Supabase: {erro}')
            return render(request, "add-integrante.html", {'dados': request.POST})

        messages.success(request, 'Integrante cadastrado com sucesso.')
        return redirect("integrantes")

    return render(request, "add-integrante.html")


@login_required
def editIntegrante(request, id_integrante):
    if request.method == "POST":
        dados = {
            "nome": request.POST.get("nome"),
            "cargo": request.POST.get("cargo"),
            "biografia": request.POST.get("biografia"),
        }
        try:
            foto = _foto_do_formulario(request)
            if foto is not SEM_ALTERACAO:  # só altera a foto se enviou uma nova ou pediu para remover
                dados["foto_url"] = foto
            resposta = supabase.table("integrantes").update(dados).eq("id", id_integrante).execute()
            if not resposta.data:
                # Sem linhas devolvidas: o Supabase bloqueou (RLS) ou o integrante não existe
                raise ErroUpload('O Supabase não confirmou a alteração (verifique a policy de UPDATE da tabela integrantes).')
        except ErroUpload as erro:
            messages.error(request, str(erro))
            return render(request, "edit-integrante.html", {'integrante': {**dados, "id": id_integrante, "foto_url": request.POST.get("foto_atual")}})
        except Exception as erro:
            messages.error(request, f'Não foi possível salvar no Supabase: {erro}')
            return render(request, "edit-integrante.html", {'integrante': {**dados, "id": id_integrante, "foto_url": request.POST.get("foto_atual")}})

        messages.success(request, 'Integrante atualizado com sucesso.')
        return redirect("integrantes")

    resposta = supabase.table("integrantes").select("*").eq("id", id_integrante).execute()
    if not resposta.data:
        messages.error(request, 'Integrante não encontrado.')
        return redirect("integrantes")

    return render(request, "edit-integrante.html", {'integrante': resposta.data[0]})


@login_required
@require_POST
def delIntegrantes(request, id_integrante):
    supabase.table("integrantes").delete().eq("id", id_integrante).execute()
    messages.success(request, 'Integrante excluído.')
    return redirect("integrantes")
