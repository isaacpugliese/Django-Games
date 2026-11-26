from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import CadastroForm
from .models import Perfil
# Create your views here.


def _eh_admin(usuario, perfil):
    return usuario.is_superuser or perfil.tipo_usuario.lower() == 'administrador'


@login_required
def dashboard(request):
    # get_or_create evita erro 500 para usuários criados sem Perfil (ex.: createsuperuser)
    perfil, _ = Perfil.objects.get_or_create(
        usuario=request.user,
        defaults={'tipo_usuario': 'administrador' if request.user.is_superuser else 'cliente'},
    )

    if _eh_admin(request.user, perfil):
        return redirect("/admin/")

    return render(request, "dashboard.html")

@login_required
def perfil(request):
    if request.method == "POST":
        usuario = request.user

        usuario.first_name = request.POST.get("nome")
        usuario.last_name = request.POST.get("sobrenome")
        usuario.email = request.POST.get("email")

        usuario.save()

        messages.success(request, 'Dados atualizados com sucesso.')
        return redirect("perfil")


    return render(request, "perfil.html")


def cadastro(request):
    if request.method == "POST":
        # form = UserCreationForm(request.POST)
        form = CadastroForm(request.POST)

        if form.is_valid():
            usuario = form.save()
            Perfil.objects.create(usuario=usuario, tipo_usuario='cliente')
            messages.success(request, 'Conta criada com sucesso! Faça login para continuar.')
            return redirect('login')
    else:
        # form = UserCreationForm()
        form = CadastroForm()

    return render(request, "cadastro.html", {'form': form})
