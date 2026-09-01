"""Pacote raiz do backend.

Este arquivo existe (mesmo vazio) para que o Python trate a pasta "backend"
como um PACOTE. E' isso que permite rodar comandos como:

    python -m backend.seed
    uvicorn backend.app.main:app --reload

sempre a partir da raiz do projeto.
"""
