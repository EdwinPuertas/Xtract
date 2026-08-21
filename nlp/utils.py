import traceback


class Utils:
    @staticmethod
    def standard_error(exc_info):
        exc_type, exc_value, exc_tb = exc_info
        traceback.print_exception(exc_type, exc_value, exc_tb)
