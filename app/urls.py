from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.index, name="index"),
    path("quem-somos/", views.quem_somos, name="quem_somos"),
    path("servicos", views.servicos, name="servicos"),
    path("add-servico", views.addServico, name="addServico"),
    path("del-servico/<int:id_servico>", views.delServico, name="delServico"),
    path("edit-servico/<int:id_servico>", views.editServico, name="editServico"),  
    path('produtos/', views.produto, name='produtos'),

    
    path("integrantes", views.integrantes,name="integrantes"),
    path("add-integrante", views.addIntegrante,name="addIntegrante"),
    path("edit-integrante/<int:id_integrante>/", views.editIntegrante, name="editIntegrante"),
    
    path("del-integrante/<int:id_integrante>/", views.delIntegrantes,name="delIntegrante"),
    
    path('categoria-api/', views.categoriasAPI,name="categoriasAPI"),
    path('categoria-api/<int:id_categoria>/', views.categoriaAPI,name="categoriaAPI"),
    
    path('relatorios/', views.relatorios, name='relatorios'),

    path('comprar/<int:id_servico>/', views.comprar, name='comprar'),
    path('meus-pedidos/', views.meus_pedidos, name='meus_pedidos'),
    path('meus-pedidos/remover/<int:id_pedido>/', views.remover_pedido, name='remover_pedido'),
]
