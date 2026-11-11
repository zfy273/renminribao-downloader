use std::process::Command;

#[test]
fn init_writes_toml_configuration() {
    let temp = tempfile::tempdir().unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_rmrb-downloader"))
        .current_dir(temp.path())
        .arg("init")
        .output()
        .unwrap();
    assert!(output.status.success());
    assert!(temp.path().join("config.toml").exists());
    assert!(!temp.path().join("config.json").exists());
}

#[test]
fn config_command_displays_toml() {
    let temp = tempfile::tempdir().unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_rmrb-downloader"))
        .current_dir(temp.path())
        .arg("config")
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("配置文件:"));
    assert!(stdout.contains("[network]"));
}

#[test]
fn check_date_accepts_valid_date_and_rejects_invalid_date() {
    let binary = env!("CARGO_BIN_EXE_rmrb-downloader");
    let temp = tempfile::tempdir().unwrap();
    let valid = Command::new(binary)
        .current_dir(temp.path())
        .args(["check-date", "20260903"])
        .output()
        .unwrap();
    assert!(valid.status.success());
    assert!(String::from_utf8_lossy(&valid.stdout).contains("2026-09-03"));

    let invalid = Command::new(binary)
        .current_dir(temp.path())
        .args(["check-date", "20260230"])
        .output()
        .unwrap();
    assert!(!invalid.status.success());
}
