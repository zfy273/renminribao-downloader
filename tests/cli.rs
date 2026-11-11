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
