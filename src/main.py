def run_console():
    """Ejecuta el procesamiento en modo consola."""
    from src.storage_service import StorageService
    service = StorageService()
    result = service.process_all()
    service.save_results(result)
    
    print(f"\nProcessed {len(result.processed_files)} files")
    print(f"Skipped {len(result.skipped_files)} files" + f" ({', '.join(result.skipped_files)})" if result.skipped_files else "")
    print(f"Protocols with errors: {len(result.error_protocols['PROTOCOL'].unique())}")
    print(f"Max values calculated for {len(result.max_values['PROTOCOL'].unique())} protocols")


def run_gui():
    """Ejecuta la interfaz gráfica."""
    from src.gui import MaxStorageGUI
    app = MaxStorageGUI()
    app.run()


def main():
    # run_console()
    run_gui()


if __name__ == "__main__":
    main()