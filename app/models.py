from django.conf import settings
from django.db import models

# Create your models here.
class Contato(models.Model):
    nome = models.CharField(max_length=100)
    email = models.EmailField()
    telefone = models.CharField(max_length=20, blank=True)
    mensagem = models.TextField()

class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nome

class Servico(models.Model):
    nome = models.CharField(max_length=150)  
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    imagem = models.ImageField(upload_to='servicos/', blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='servicos', blank=True, null=True)

    def __str__(self):
        return self.nome


class Pedido(models.Model):
    """Compra de um serviço feita por um cliente autenticado.

    nome_servico e preco guardam uma 'foto' do serviço no momento da compra,
    para o histórico não mudar se o serviço for editado ou excluído depois.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pedidos')
    servico = models.ForeignKey(Servico, on_delete=models.SET_NULL, related_name='pedidos', blank=True, null=True)
    nome_servico = models.CharField(max_length=150)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.usuario} - {self.nome_servico}'
