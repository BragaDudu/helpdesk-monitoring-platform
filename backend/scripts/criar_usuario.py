#!/usr/bin/env python3
"""Script interativo para criar novo usuário e cliente."""

import sys
from pathlib import Path

# Adiciona o diretório pai ao PATH para importar backend
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.database import SessionLocal
from backend.app.models import Client, User
from backend.app.security import hash_senha
from backend.app.enums import UserRole


def criar_cliente_e_usuario():
    """Cria um novo cliente e um usuário administrador para ele."""

    db = SessionLocal()

    try:
        print("\n" + "="*60)
        print("CRIAR NOVO CLIENTE E USUÁRIO")
        print("="*60 + "\n")

        # ─────────────────────────────────────────────────────────────
        # DADOS DO CLIENTE (EMPRESA)
        # ─────────────────────────────────────────────────────────────
        print("📋 DADOS DO CLIENTE (EMPRESA)")
        print("-" * 60)

        nome_contato = input("Nome do contato principal: ").strip()
        if not nome_contato:
            print("❌ Nome é obrigatório.")
            return

        razao_social = input("Razão social / Nome da empresa: ").strip()
        if not razao_social:
            print("❌ Razão social é obrigatória.")
            return

        email_empresa = input("E-mail da empresa: ").strip().lower()
        if not email_empresa or "@" not in email_empresa:
            print("❌ E-mail inválido.")
            return

        telefone = input("Telefone (ex: +55 11 98765-4321): ").strip()
        if not telefone:
            print("❌ Telefone é obrigatório.")
            return

        # Verifica se empresa já existe
        existente = db.query(Client).filter(Client.email == email_empresa).first()
        if existente:
            print(f"❌ Já existe empresa cadastrada com este e-mail: {email_empresa}")
            return

        # ─────────────────────────────────────────────────────────────
        # DADOS DO USUÁRIO
        # ─────────────────────────────────────────────────────────────
        print("\n👤 DADOS DO USUÁRIO ADMINISTRADOR")
        print("-" * 60)

        email_usuario = input("E-mail do administrador: ").strip().lower()
        if not email_usuario or "@" not in email_usuario:
            print("❌ E-mail inválido.")
            return

        # Verifica se usuário já existe
        existente = db.query(User).filter(User.email == email_usuario).first()
        if existente:
            print(f"❌ Já existe usuário com este e-mail: {email_usuario}")
            return

        nome_usuario = input("Nome do administrador: ").strip()
        if not nome_usuario:
            print("❌ Nome é obrigatório.")
            return

        while True:
            senha = input("Senha (mínimo 8 caracteres): ").strip()
            if len(senha) < 8:
                print("❌ Senha deve ter no mínimo 8 caracteres.")
                continue
            if len(senha) > 128:
                print("❌ Senha muito longa (máximo 128 caracteres).")
                continue
            break

        # ─────────────────────────────────────────────────────────────
        # RESUMO E CONFIRMAÇÃO
        # ─────────────────────────────────────────────────────────────
        print("\n" + "="*60)
        print("RESUMO DO CADASTRO")
        print("="*60)
        print(f"\n📦 Cliente:")
        print(f"   Empresa: {razao_social}")
        print(f"   Contato: {nome_contato}")
        print(f"   E-mail: {email_empresa}")
        print(f"   Telefone: {telefone}")
        print(f"\n👤 Usuário:")
        print(f"   E-mail: {email_usuario}")
        print(f"   Nome: {nome_usuario}")
        print(f"   Papel: ADMIN_EMPRESA (acesso só a esta empresa)")

        confirmacao = input("\n✓ Deseja criar? (s/n): ").strip().lower()
        if confirmacao != 's':
            print("❌ Operação cancelada.")
            return

        # ─────────────────────────────────────────────────────────────
        # CRIAR NO BANCO
        # ─────────────────────────────────────────────────────────────
        print("\n⏳ Criando cliente...")
        novo_cliente = Client(
            name=nome_contato,
            company=razao_social,
            email=email_empresa,
            phone=telefone
        )
        db.add(novo_cliente)
        db.flush()  # Gera o ID sem fazer commit ainda

        print(f"✓ Cliente criado com ID {novo_cliente.id}")

        print("⏳ Criando usuário...")
        novo_usuario = User(
            email=email_usuario,
            password_hash=hash_senha(senha),
            name=nome_usuario,
            role=UserRole.ADMIN_EMPRESA,
            client_id=novo_cliente.id,
            is_active=True
        )
        db.add(novo_usuario)

        print(f"✓ Usuário criado com ID {novo_usuario.id}")

        db.commit()

        # ─────────────────────────────────────────────────────────────
        # SUCESSO
        # ─────────────────────────────────────────────────────────────
        print("\n" + "="*60)
        print("✅ CADASTRO CONCLUÍDO COM SUCESSO!")
        print("="*60)
        print(f"\n🎉 Nova empresa: {razao_social}")
        print(f"\n📍 Faça login com:")
        print(f"   E-mail: {email_usuario}")
        print(f"   Senha: {'*' * len(senha)}")
        print(f"\n🔒 Dados salvos no banco de dados.")
        print(f"   Cliente ID: {novo_cliente.id}")
        print(f"   Usuário ID: {novo_usuario.id}\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro ao criar: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    criar_cliente_e_usuario()
