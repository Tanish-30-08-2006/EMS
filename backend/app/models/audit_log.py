class AuditLog:
    def __init__(self, log_id, table_name, operation, old_data, new_data, changed_at):
        self.log_id = log_id
        self.table_name = table_name
        self.operation = operation
        self.old_data = old_data   # This will be a dictionary
        self.new_data = new_data   # This will be a dictionary
        self.changed_at = changed_at