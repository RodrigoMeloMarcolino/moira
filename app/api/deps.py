from functools import cached_property
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.modules.appointments.application.use_cases import BookPublicAppointmentUseCase
from app.modules.appointments.infrastructure.repositories import (
    SQLAlchemyAppointmentRepository,
    SQLAlchemyAppointmentSlotRepository,
)
from app.modules.auth.infrastructure.passwords import BcryptPasswordHasher
from app.modules.availability.application.use_cases import (
    CreateAvailabilityRuleUseCase,
    ListProviderAvailabilityRulesUseCase,
    ListProviderAvailableSlotsUseCase,
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
from app.modules.users.application.use_cases import CreateUserUseCase
from app.modules.users.infrastructure.repositories import SqlAlchemyUserRepository
from app.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class RequestContainer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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


def build_request_container(session: SessionDep) -> RequestContainer:
    return RequestContainer(session)


RequestContainerDep = Annotated[RequestContainer, Depends(build_request_container)]


def build_signup_provider_use_case(
    container: RequestContainerDep,
) -> SignupProviderUseCase:
    return SignupProviderUseCase(
        create_user=container.create_user_use_case,
        providers=container.providers,
        unit_of_work=container.unit_of_work,
    )


def build_get_provider_by_slug_use_case(
    container: RequestContainerDep,
) -> GetProviderBySlugUseCase:
    return GetProviderBySlugUseCase(
        providers=container.providers,
    )


def build_create_offering_use_case(
    container: RequestContainerDep,
) -> CreateOfferingUseCase:
    return CreateOfferingUseCase(
        providers=container.providers,
        offerings=container.offerings,
        unit_of_work=container.unit_of_work,
    )


def build_list_active_provider_offerings_use_case(
    container: RequestContainerDep,
) -> ListActiveProviderOfferingsUseCase:
    return ListActiveProviderOfferingsUseCase(
        providers=container.providers,
        offerings=container.offerings,
    )


def build_update_offering_use_case(
    container: RequestContainerDep,
) -> UpdateOfferingUseCase:
    return UpdateOfferingUseCase(
        offerings=container.offerings,
        unit_of_work=container.unit_of_work,
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
    )


def build_create_provider_availability_use_case(
    container: RequestContainerDep,
) -> CreateAvailabilityRuleUseCase:
    return CreateAvailabilityRuleUseCase(
        availability_rules=container.availability_rules,
        providers=container.providers,
        uow=container.unit_of_work,
    )


def build_list_provider_availability_rules_use_case(
    container: RequestContainerDep,
) -> ListProviderAvailabilityRulesUseCase:
    return ListProviderAvailabilityRulesUseCase(
        availability_rules=container.availability_rules,
        providers=container.providers,
    )


def build_list_provider_available_slots_use_case(
    container: RequestContainerDep,
) -> ListProviderAvailableSlotsUseCase:
    return container.list_provider_available_slots_use_case


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
BookPublicAppointmentUseCaseDep = Annotated[
    BookPublicAppointmentUseCase,
    Depends(build_book_public_appointment_use_case),
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
