from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.modules.auth.infrastructure.passwords import BcryptPasswordHasher
from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.offerings.application.use_cases import (
    CreateOfferingUseCase,
    ListActiveProviderOfferingsUseCase,
    UpdateOfferingUseCase,
)
from app.modules.offerings.infrastructure.repositories import (
    SqlAlchemyOfferingRepository,
)
from app.modules.providers.application.use_cases import (
    GetProviderBySlugUseCase,
    SignupProviderUseCase,
)
from app.modules.providers.infrastructure.repositories import (
    SqlAlchemyProviderRepository,
)
from app.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def build_signup_provider_use_case(session: SessionDep) -> SignupProviderUseCase:
    return SignupProviderUseCase(
        users=SqlAlchemyUserRepository(session),
        providers=SqlAlchemyProviderRepository(session),
        password_hasher=BcryptPasswordHasher(),
        unit_of_work=SqlAlchemyUnitOfWork(session),
    )


def build_get_provider_by_slug_use_case(
    session: SessionDep,
) -> GetProviderBySlugUseCase:
    return GetProviderBySlugUseCase(
        providers=SqlAlchemyProviderRepository(session),
    )


def build_create_offering_use_case(session: SessionDep) -> CreateOfferingUseCase:
    return CreateOfferingUseCase(
        providers=SqlAlchemyProviderRepository(session),
        offerings=SqlAlchemyOfferingRepository(session),
        unit_of_work=SqlAlchemyUnitOfWork(session),
    )


def build_list_active_provider_offerings_use_case(
    session: SessionDep,
) -> ListActiveProviderOfferingsUseCase:
    return ListActiveProviderOfferingsUseCase(
        providers=SqlAlchemyProviderRepository(session),
        offerings=SqlAlchemyOfferingRepository(session),
    )


def build_update_offering_use_case(session: SessionDep) -> UpdateOfferingUseCase:
    return UpdateOfferingUseCase(
        offerings=SqlAlchemyOfferingRepository(session),
        unit_of_work=SqlAlchemyUnitOfWork(session),
    )


SignupProviderUseCaseDep = Annotated[
    SignupProviderUseCase,
    Depends(build_signup_provider_use_case),
]
GetProviderBySlugUseCaseDep = Annotated[
    GetProviderBySlugUseCase,
    Depends(build_get_provider_by_slug_use_case),
]
CreateOfferingUseCaseDep = Annotated[
    CreateOfferingUseCase,
    Depends(build_create_offering_use_case),
]
ListActiveProviderOfferingsUseCaseDep = Annotated[
    ListActiveProviderOfferingsUseCase,
    Depends(build_list_active_provider_offerings_use_case),
]
UpdateOfferingUseCaseDep = Annotated[
    UpdateOfferingUseCase,
    Depends(build_update_offering_use_case),
]
