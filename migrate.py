import os

files = [
    "frontend/context/AuthContext.js",
    "frontend/services/api.js",
    "frontend/pages/settings.js",
    "frontend/pages/portfolio.js",
    "frontend/context/ThemeContext.js",
    "frontend/pages/index.js"
]

for filepath in files:
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}, does not exist.")
        continue
        
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Add migration block to AuthContext.js
    if "AuthContext.js" in filepath:
        migration_block = """  // On mount, restore session from localStorage, sessionStorage, or cookie
  useEffect(() => {
    // --- ONE-TIME MIGRATION FOR RENAMING ntrade_ TO invexo_ ---
    if (typeof window !== "undefined") {
      try {
        const keysToMigrate = [];
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith("ntrade_")) {
            keysToMigrate.push(key);
          }
        }
        keysToMigrate.forEach(key => {
          const val = localStorage.getItem(key);
          const newKey = key.replace("ntrade_", "invexo_");
          localStorage.setItem(newKey, val);
          localStorage.removeItem(key);
        });
        
        const ssToken = sessionStorage.getItem("ntrade_token");
        if (ssToken !== null) {
            sessionStorage.setItem("invexo_token", ssToken);
            sessionStorage.removeItem("ntrade_token");
        }

        const cookieToken = getCookie("ntrade_token");
        if (cookieToken) {
            setCookie("invexo_token", cookieToken, 30);
            eraseCookie("ntrade_token");
        }
      } catch (err) {
        console.error("Migration failed:", err);
      }
    }
    // --- END MIGRATION ---

    const stored ="""
        content = content.replace(
            "  // On mount, restore session from localStorage, sessionStorage, or cookie\n  useEffect(() => {\n    const stored =",
            migration_block
        )
    
    # Replace all occurrences of ntrade_ with invexo_
    new_content = content.replace("ntrade_", "invexo_")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"Successfully processed {filepath}")

