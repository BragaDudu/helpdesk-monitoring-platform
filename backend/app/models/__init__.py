"""Reune todos os models num unico ponto de importacao.

POR QUE ESTE ARQUIVO E' NECESSARIO (e nao apenas conveniente):

    Base.metadata.create_all(engine) so cria as tabelas que o SQLAlchemy
    JA CONHECE. E ele so conhece uma classe depois que o arquivo dela foi
    importado ao menos uma vez.

    Se ninguem importasse models/alert.py, a tabela "alerts" simplesmente
    nao seria criada -- sem nenhum erro, o que e' pior.

    Importando tudo aqui, basta um "import backend.app.models" para que as
    cinco tabelas estejam registradas.
"""

from backend.app.models.alert import Alert
from backend.app.models.client import Client
from backend.app.models.equipment import Equipment
from backend.app.models.reading import EquipmentReading
from backend.app.models.ticket import Ticket

__all__ = ["Alert", "Client", "Equipment", "EquipmentReading", "Ticket"]
