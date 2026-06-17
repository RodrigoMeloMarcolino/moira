class AppointmentError(Exception):
    pass


class InvalidAppointmentStart(AppointmentError):
    pass


class OfferingDoesNotBelongToProvider(AppointmentError):
    pass


class AppointmentBookingConflict(AppointmentError):
    pass


class AppointmentStartUnavailable(AppointmentError):
    pass
