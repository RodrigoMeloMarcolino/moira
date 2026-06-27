import logging
from datetime import timedelta
from functools import cached_property
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.modules.appointments.application.use_cases import (
    BookPublicAppointmentUseCase,
    ListProviderAppointmentsUseCase,
)
from app.modules.appointments.infrastructure.repositories import (
    SQLAlchemyAppointmentRepository,
    SQLAlchemyAppointmentSlotRepository,
)
from app.modules.auth.application.exceptions import InvalidAccessToken
from app.modules.auth.application.use_cases import LoginProviderUseCase
from app.modules.auth.infrastructure.passwords import BcryptPasswordHasher
from app.modules.auth.infrastructure.tokens import HmacJwtAccessTokenCodec
from app.modules.availability.application.public_cache import (
    RedisPublicAvailabilityCache,
)
from app.modules.availability.application.use_cases import (
    CreateAvailabilityRuleUseCase,
    ListProviderAvailabilityRulesUseCase,
    ListProviderAvailableSlotsUseCase,
    ListPublicProviderAvailableSlotsUseCase,
    UpdateProviderAvailabilityRuleUseCase,
)
from app.modules.availability.infrastructure.repositories import (
    SQLAlchemyAvailabilityRulesRepository,
)
from app.modules.customers.application.use_cases import (
    GetOrCreateCustomerByPhoneUseCase,
)
from app.modules.customers.infrastructure.repositories import (
    SQLAlchemyCustomerRepository,
)
from app.modules.offerings.application.public_cache import PublicOfferingsCache
from app.modules.offerings.application.use_cases import (
    CreateOfferingUseCase,
    ListActiveProviderOfferingsUseCase,
    ListProviderOfferingsUseCase,
    ListPublicProviderOfferingsUseCase,
    UpdateOfferingUseCase,
)
from app.modules.offerings.infrastructure.repositories import (
    SqlAlchemyOfferingRepository,
)
from app.modules.providers.application.public_cache import ProviderCatalogCache
from app.modules.providers.application.use_cases import (
    GetProviderBySlugUseCase,
    GetPublicProviderBySlugUseCase,
    SignupProviderUseCase,
)
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.infrastructure.repositories import (
    SqlAlchemyProviderRepository,
)
from app.modules.users.application.use_cases import CreateUserUseCase
from app.modules.users.infrastructure.repositories import SqlAlchemyUserRepository
from app.shared.application.cache import AsyncCache
from app.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
bearer_scheme = HTTPBearer(auto_error=False)


class RequestContainer:
    def __init__(
        self,
        session: AsyncSession,
        cache_backend: AsyncCache,
    ) -> None:
        self.session = session
        self.cache_backend = cache_backend

    @cached_property
    def users(self) -> SqlAlchemyUserRepository:
        return SqlAlchemyUserRepository(self.session)

    @cached_property
    def providers(self) -> SqlAlchemyProviderRepository:
        return SqlAlchemyProviderRepository(self.session)

    @cached_property
    def offerings(self) -> SqlAlchemyOfferingRepository:
        return SqlAlchemyOfferingRepository(self.session)

    @cached_property
    def customers(self) -> SQLAlchemyCustomerRepository:
        return SQLAlchemyCustomerRepository(self.session)

    @cached_property
    def appointments(self) -> SQLAlchemyAppointmentRepository:
        return SQLAlchemyAppointmentRepository(self.session)

    @cached_property
    def appointment_slots(self) -> SQLAlchemyAppointmentSlotRepository:
        return SQLAlchemyAppointmentSlotRepository(self.session)

    @cached_property
    def availability_rules(self) -> SQLAlchemyAvailabilityRulesRepository:
        return SQLAlchemyAvailabilityRulesRepository(self.session)

    @cached_property
    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session)

    @cached_property
    def password_hasher(self) -> BcryptPasswordHasher:
        return BcryptPasswordHasher()

    @cached_property
    def access_tokens(self) -> HmacJwtAccessTokenCodec:
        settings = get_settings()
        return HmacJwtAccessTokenCodec(
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            expires_delta=timedelta(
                minutes=settings.jwt_access_token_expire_minutes,
            ),
        )

    @cached_property
    def create_user_use_case(self) -> CreateUserUseCase:
        return CreateUserUseCase(
            users=self.users,
            password_hasher=self.password_hasher,
        )

    @cached_property
    def get_or_create_customer_by_phone_use_case(
        self,
    ) -> GetOrCreateCustomerByPhoneUseCase:
        return GetOrCreateCustomerByPhoneUseCase(customers=self.customers)

    @cached_property
    def list_provider_available_slots_use_case(
        self,
    ) -> ListProviderAvailableSlotsUseCase:
        return ListProviderAvailableSlotsUseCase(
            providers=self.providers,
            appointment_slots=self.appointment_slots,
            offerings=self.offerings,
            rules=self.availability_rules,
        )

    @cached_property
    def login_provider_use_case(self) -> LoginProviderUseCase:
        settings = get_settings()
        return LoginProviderUseCase(
            users=self.users,
            providers=self.providers,
            password_hasher=self.password_hasher,
            access_tokens=self.access_tokens,
            access_token_expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    @cached_property
    def get_provider_by_slug_use_case(self) -> GetProviderBySlugUseCase:
        return GetProviderBySlugUseCase(providers=self.providers)

    @cached_property
    def provider_catalog_cache(self) -> ProviderCatalogCache:
        settings = get_settings()
        return ProviderCatalogCache(
            self.cache_backend,
            ttl_seconds=settings.cache_ttl_public_provider_seconds,
        )

    @cached_property
    def public_offerings_cache(self) -> PublicOfferingsCache:
        settings = get_settings()
        return PublicOfferingsCache(
            self.cache_backend,
            ttl_seconds=settings.cache_ttl_public_offerings_seconds,
        )

    @cached_property
    def public_availability_cache(self) -> RedisPublicAvailabilityCache:
        settings = get_settings()
        return RedisPublicAvailabilityCache(
            self.cache_backend,
            slots_ttl_seconds=settings.cache_ttl_available_slots_seconds,
        )

    @cached_property
    def get_public_provider_by_slug_use_case(self) -> GetPublicProviderBySlugUseCase:
        return GetPublicProviderBySlugUseCase(
            providers=self.providers,
            public_cache=self.provider_catalog_cache,
        )

    @cached_property
    def list_public_provider_offerings_use_case(
        self,
    ) -> ListPublicProviderOfferingsUseCase:
        return ListPublicProviderOfferingsUseCase(
            providers=self.providers,
            offerings=self.offerings,
            public_cache=self.public_offerings_cache,
        )

    @cached_property
    def list_public_provider_available_slots_use_case(
        self,
    ) -> ListPublicProviderAvailableSlotsUseCase:
        return ListPublicProviderAvailableSlotsUseCase(
            providers=self.providers,
            offerings=self.offerings,
            list_provider_available_slots=self.list_provider_available_slots_use_case,
            public_cache=self.public_availability_cache,
        )

    @cached_property
    def list_active_provider_offerings_use_case(
        self,
    ) -> ListActiveProviderOfferingsUseCase:
        return ListActiveProviderOfferingsUseCase(
            providers=self.providers,
            offerings=self.offerings,
        )


def build_request_container(
    request: Request,
    session: SessionDep,
) -> RequestContainer:
    return RequestContainer(session, request.app.state.cache_backend)


RequestContainerDep = Annotated[RequestContainer, Depends(build_request_container)]


async def get_current_provider(
    container: RequestContainerDep,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(bearer_scheme),
    ],
) -> Provider:
    if credentials is None:
        logger.info(
            'Access rejected because credentials are missing',
            extra={
                'event_name': 'auth.access_rejected',
                'reason': 'missing_credentials',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='authentication required',
        )

    try:
        user_id = container.access_tokens.verify_access_token(credentials.credentials)
    except InvalidAccessToken:
        logger.info(
            'Access rejected because the token is invalid',
            extra={
                'event_name': 'auth.access_rejected',
                'reason': 'invalid_token',
            },
        )
        raise

    user = await container.users.get_by_id(user_id)
    if user is None:
        logger.info(
            'Access rejected because the user was not found',
            extra={
                'event_name': 'auth.access_rejected',
                'reason': 'user_not_found',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid access token',
        )

    provider = await container.providers.get_by_user_id(user.id)
    if provider is None:
        logger.info(
            'Access rejected because the provider was not found',
            extra={
                'event_name': 'auth.access_rejected',
                'reason': 'provider_not_found',
                'user.id': user.id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid access token',
        )

    return provider


CurrentProviderDep = Annotated[Provider, Depends(get_current_provider)]


def build_signup_provider_use_case(
    container: RequestContainerDep,
) -> SignupProviderUseCase:
    settings = get_settings()
    return SignupProviderUseCase(
        create_user=container.create_user_use_case,
        providers=container.providers,
        unit_of_work=container.unit_of_work,
        default_timezone=settings.default_timezone,
    )


def build_login_provider_use_case(
    container: RequestContainerDep,
) -> LoginProviderUseCase:
    return container.login_provider_use_case


def build_get_provider_by_slug_use_case(
    container: RequestContainerDep,
) -> GetProviderBySlugUseCase:
    return container.get_provider_by_slug_use_case


def build_create_offering_use_case(
    container: RequestContainerDep,
) -> CreateOfferingUseCase:
    return CreateOfferingUseCase(
        offerings=container.offerings,
        unit_of_work=container.unit_of_work,
        public_offerings_cache=container.public_offerings_cache,
    )


def build_list_active_provider_offerings_use_case(
    container: RequestContainerDep,
) -> ListActiveProviderOfferingsUseCase:
    return container.list_active_provider_offerings_use_case


def build_list_provider_offerings_use_case(
    container: RequestContainerDep,
) -> ListProviderOfferingsUseCase:
    return ListProviderOfferingsUseCase(
        offerings=container.offerings,
    )


def build_update_offering_use_case(
    container: RequestContainerDep,
) -> UpdateOfferingUseCase:
    return UpdateOfferingUseCase(
        offerings=container.offerings,
        unit_of_work=container.unit_of_work,
        public_offerings_cache=container.public_offerings_cache,
        public_availability_cache=container.public_availability_cache,
    )


def build_book_public_appointment_use_case(
    container: RequestContainerDep,
) -> BookPublicAppointmentUseCase:
    return BookPublicAppointmentUseCase(
        appointments=container.appointments,
        appointment_slots=container.appointment_slots,
        offerings=container.offerings,
        providers=container.providers,
        get_or_create_customer_by_phone=(
            container.get_or_create_customer_by_phone_use_case
        ),
        list_provider_available_slots=container.list_provider_available_slots_use_case,
        uow=container.unit_of_work,
        public_availability_cache=container.public_availability_cache,
    )


def build_create_provider_availability_use_case(
    container: RequestContainerDep,
) -> CreateAvailabilityRuleUseCase:
    return CreateAvailabilityRuleUseCase(
        availability_rules=container.availability_rules,
        uow=container.unit_of_work,
        public_availability_cache=container.public_availability_cache,
    )


def build_list_provider_availability_rules_use_case(
    container: RequestContainerDep,
) -> ListProviderAvailabilityRulesUseCase:
    return ListProviderAvailabilityRulesUseCase(
        availability_rules=container.availability_rules,
    )


def build_list_provider_available_slots_use_case(
    container: RequestContainerDep,
) -> ListProviderAvailableSlotsUseCase:
    return container.list_provider_available_slots_use_case


def build_update_provider_availability_rule_use_case(
    container: RequestContainerDep,
) -> UpdateProviderAvailabilityRuleUseCase:
    return UpdateProviderAvailabilityRuleUseCase(
        availability_rules=container.availability_rules,
        uow=container.unit_of_work,
        public_availability_cache=container.public_availability_cache,
    )


def build_list_provider_appointments_use_case(
    container: RequestContainerDep,
) -> ListProviderAppointmentsUseCase:
    return ListProviderAppointmentsUseCase(
        appointments=container.appointments,
    )


def build_get_public_provider_by_slug_use_case(
    container: RequestContainerDep,
) -> GetPublicProviderBySlugUseCase:
    return container.get_public_provider_by_slug_use_case


def build_list_public_provider_offerings_use_case(
    container: RequestContainerDep,
) -> ListPublicProviderOfferingsUseCase:
    return container.list_public_provider_offerings_use_case


def build_list_public_provider_available_slots_use_case(
    container: RequestContainerDep,
) -> ListPublicProviderAvailableSlotsUseCase:
    return container.list_public_provider_available_slots_use_case


SignupProviderUseCaseDep = Annotated[
    SignupProviderUseCase,
    Depends(build_signup_provider_use_case),
]
LoginProviderUseCaseDep = Annotated[
    LoginProviderUseCase,
    Depends(build_login_provider_use_case),
]
GetProviderBySlugUseCaseDep = Annotated[
    GetProviderBySlugUseCase,
    Depends(build_get_provider_by_slug_use_case),
]
GetPublicProviderBySlugUseCaseDep = Annotated[
    GetPublicProviderBySlugUseCase,
    Depends(build_get_public_provider_by_slug_use_case),
]
CreateOfferingUseCaseDep = Annotated[
    CreateOfferingUseCase,
    Depends(build_create_offering_use_case),
]
ListActiveProviderOfferingsUseCaseDep = Annotated[
    ListActiveProviderOfferingsUseCase,
    Depends(build_list_active_provider_offerings_use_case),
]
ListPublicProviderOfferingsUseCaseDep = Annotated[
    ListPublicProviderOfferingsUseCase,
    Depends(build_list_public_provider_offerings_use_case),
]
ListProviderOfferingsUseCaseDep = Annotated[
    ListProviderOfferingsUseCase,
    Depends(build_list_provider_offerings_use_case),
]
UpdateOfferingUseCaseDep = Annotated[
    UpdateOfferingUseCase,
    Depends(build_update_offering_use_case),
]
BookPublicAppointmentUseCaseDep = Annotated[
    BookPublicAppointmentUseCase,
    Depends(build_book_public_appointment_use_case),
]
ListProviderAppointmentsUseCaseDep = Annotated[
    ListProviderAppointmentsUseCase,
    Depends(build_list_provider_appointments_use_case),
]
CreateAvailabilityRuleUseCaseDep = Annotated[
    CreateAvailabilityRuleUseCase,
    Depends(build_create_provider_availability_use_case),
]
ListProviderAvailabilityRulesUseCaseDep = Annotated[
    ListProviderAvailabilityRulesUseCase,
    Depends(build_list_provider_availability_rules_use_case),
]
ListProviderAvailableSlotsUseCaseDep = Annotated[
    ListProviderAvailableSlotsUseCase,
    Depends(build_list_provider_available_slots_use_case),
]
ListPublicProviderAvailableSlotsUseCaseDep = Annotated[
    ListPublicProviderAvailableSlotsUseCase,
    Depends(build_list_public_provider_available_slots_use_case),
]
UpdateProviderAvailabilityRuleUseCaseDep = Annotated[
    UpdateProviderAvailabilityRuleUseCase,
    Depends(build_update_provider_availability_rule_use_case),
]
