# contato/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # URL limpa: /contato/  (é a usada pelo menu)
    path('', views.novo_contato, name='novo_contato'),
    # URL antiga (/contato/contato/) continua funcionando, sem nome para não duplicar o reverse
    path('contato/', views.novo_contato),
    path('lista/', views.lista_contatos, name='lista_contatos'),
    path('excluir/<int:id_contato>/', views.excluir_contato, name='excluir_contato'),
]
