from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .forms import ContatoForm
from .models import Contato


def novo_contato(request):
    """Formulário público: não exige login."""
    if request.method == 'POST':
        form = ContatoForm(request.POST)
        if form.is_valid():
            form.save()
            # Antes: redirect('contato_sucesso'), rota que não existe (gerava erro 500).
            messages.success(request, 'Mensagem enviada com sucesso! Em breve entraremos em contato.')
            return redirect('novo_contato')
    else:
        form = ContatoForm()
    return render(request, 'novo_contato.html', {'form': form})


@login_required
def lista_contatos(request):
    contatos = Contato.objects.all().order_by('-id')
    return render(request, 'lista_contatos.html', {'contatos': contatos})


@login_required
@require_POST
def excluir_contato(request, id_contato):
    contato = get_object_or_404(Contato, id=id_contato)
    contato.delete()
    messages.success(request, 'Contato excluído.')
    return redirect('lista_contatos')
