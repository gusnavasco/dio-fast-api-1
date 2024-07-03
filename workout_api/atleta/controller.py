from datetime import timezone, datetime
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi_pagination import LimitOffsetPage, add_pagination, paginate
from fastapi_pagination.limit_offset import LimitOffsetParams
from pydantic import UUID4
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from workout_api.centro_treinamento.models import CentroTreinamentoModel
from workout_api.categorias.models import CategoriaModel
from workout_api.atleta.models import AtletaModel
from workout_api.atleta.schemas import AtletaCustomOut, AtletaIn, AtletaOut, AtletaUpdate
from workout_api.contrib.repository.dependencies import DatabaseDependency

router = APIRouter()

@router.post(
    '/', 
    summary='Criar novo atleta', 
    status_code=status.HTTP_201_CREATED, 
    response_model=AtletaOut
)
async def post(db_session: DatabaseDependency, atleta_in: AtletaIn=Body(...)):
    nome_categoria = atleta_in.categoria.nome
    nome_centro_treinamento = atleta_in.centro_treinamento.nome

    categoria = (
        await db_session.execute(select(CategoriaModel).filter_by(nome=nome_categoria))
    ).scalars().first()

    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f'A categoria {nome_categoria} não foi encontrada.'
        )
    
    centro_treinamento = (
        await db_session.execute(select(CentroTreinamentoModel).filter_by(nome=nome_centro_treinamento))
    ).scalars().first()

    if not centro_treinamento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f'O centro de treinamento {nome_centro_treinamento} não foi encontrado.'
        )
    
    try:
        created_at_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        atleta_out = AtletaOut(id=uuid4(), created_at=created_at_naive, **atleta_in.model_dump())
        atleta_model = AtletaModel(**atleta_out.model_dump(exclude={'categoria', 'centro_treinamento'}))

        atleta_model.categoria_id = categoria.pk_id
        atleta_model.centro_treinamento_id = centro_treinamento.pk_id

        db_session.add(atleta_model)
        await db_session.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER, 
            detail=f'Já existe um atleta cadastrado com o cpf: {atleta_in.cpf}'
        )
    except Exception as exc: # Mudar exceção Exception para ficar menos genérico
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f'Ocorreu um erro ao inserir os dados no banco: {exc}'
        )
    
    return atleta_out


# @router.get(
#     '/', 
#     summary='Consultar todos os atletas', 
#     status_code=status.HTTP_200_OK, 
#     response_model=list[AtletaOut],
# )
# async def query(
#     db_session: DatabaseDependency,
#     nome: str = Query(None, description="Nome do atleta"),
#     cpf: str = Query(None, description="CPF do atleta")
# ): #-> list[AtletaOut]
#     # query = select(AtletaModel)

#     query = select(AtletaModel).options(
#         selectinload(AtletaModel.centro_treinamento),  # Carregar o relacionamento
#         selectinload(AtletaModel.categoria)            # Carregar o relacionamento
#     )
    
#     if nome:
#         query = query.filter(AtletaModel.nome == nome)
#     if cpf:
#         query = query.filter(AtletaModel.cpf == cpf)
    
#     atletas: list[AtletaOut] = (await db_session.execute(query)).scalars().all() # Mudei de AtletaOut para AtletaModel
    
#     # return [AtletaOut.model_validate(atleta) for atleta in atletas]
    
#     resultados = [AtletaOut.model_validate(atleta) for atleta in atletas]
#     res = {}

#     for atleta in resultados:
#         res.update({"nome": atleta.nome})
#         res.update({"centro_treinamento": atleta.centro_treinamento})
#         res.update({"categoria": atleta.categoria})
    
#     return res
#     # return [
#     #     AtletaCustomOut(
#     #         nome=atleta.nome,
#     #         centro_treinamento=atleta.centro_treinamento.nome if atleta.centro_treinamento else None,
#     #         categoria=atleta.categoria.nome if atleta.categoria else None
#     #     ) 
#     #     for atleta in atletas
#     # ]


# @router.get(
#     '/', 
#     summary='Consultar todos os atletas', 
#     status_code=status.HTTP_200_OK, 
#     response_model=list[AtletaCustomOut],
# )
# async def query(
#     db_session: DatabaseDependency,
#     nome: str = Query(None, description="Nome do atleta"),
#     cpf: str = Query(None, description="CPF do atleta")
# ) -> list[AtletaCustomOut]:
#     query = select(AtletaModel)
    
#     if nome:
#         query = query.filter(AtletaModel.nome == nome)
#     if cpf:
#         query = query.filter(AtletaModel.cpf == cpf)

#     atletas: list[AtletaModel] = (await db_session.execute(query)).scalars().all()
    
#     return [
#         AtletaCustomOut(
#             nome=atleta.nome,
#             centro_treinamento=atleta.centro_treinamento.nome,
#             categoria=atleta.categoria.nome
#         ) 
#         for atleta in atletas
#     ]


@router.get(
    '/',
    summary='Listar todos os atletas',
    status_code=status.HTTP_200_OK,
    response_model=LimitOffsetPage[AtletaCustomOut],
)
async def get_all(
    db_session: DatabaseDependency,
    nome: Optional[str] = None,
    cpf: Optional[str] = None,
    params: LimitOffsetParams = Depends()
) -> LimitOffsetPage[AtletaCustomOut]:
    query = select(AtletaModel)
    
    if nome:
        query = query.where(AtletaModel.nome == nome)
    if cpf:
        query = query.where(AtletaModel.cpf == cpf)
    
    result = await db_session.execute(query)
    atletas = result.scalars().all()
    
    atletas_out = [
        AtletaCustomOut(
            nome=atleta.nome,
            centro_treinamento=atleta.centro_treinamento.nome,
            categoria=atleta.categoria.nome
        ) 
        for atleta in atletas
    ]
    
    return paginate(atletas_out)


@router.get(
    '/{id}', 
    summary='Consultar um atleta pelo id', 
    status_code=status.HTTP_200_OK, 
    response_model=AtletaOut,
)
async def query(id: UUID4, db_session: DatabaseDependency) -> AtletaOut:
    atleta: AtletaOut = (
        await db_session.execute(select(AtletaModel).filter_by(id=id))
    ).scalars().first()
    
    if not atleta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f'Atleta não encontrado no id: {id}'
        )
    
    return atleta


@router.patch(
    '/{id}', 
    summary='Editar um atleta pelo id', 
    status_code=status.HTTP_200_OK, 
    response_model=AtletaOut,
)
async def query(id: UUID4, db_session: DatabaseDependency, atleta_up: AtletaUpdate=Body(...)) -> AtletaOut:
    atleta: AtletaOut = (
        await db_session.execute(select(AtletaModel).filter_by(id=id))
    ).scalars().first()
    
    if not atleta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f'Atleta não encontrado no id: {id}'
        )
    
    atleta_update = atleta_up.model_dump(exclude_unset=True)

    for key, value in atleta_update.items():
        setattr(atleta, key, value)
    
    await db_session.commit()
    await db_session.refresh(atleta)

    return atleta


@router.delete(
    '/{id}', 
    summary='Deletar um atleta pelo id', 
    status_code=status.HTTP_204_NO_CONTENT
)
async def query(id: UUID4, db_session: DatabaseDependency) -> None:
    atleta: AtletaOut = (
        await db_session.execute(select(AtletaModel).filter_by(id=id))
    ).scalars().first()
    
    if not atleta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f'Atleta não encontrado no id: {id}'
        )
    
    await db_session.delete(atleta)
    await db_session.commit()

add_pagination(router)
