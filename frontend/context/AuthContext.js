import { createContext, useContext, useState, useEffect } from "react";
import API from "../services/api";

const resizeImage = (base64Str, maxWidth = 150, maxHeight = 150) => {
  return new Promise((resolve) => {
    if (typeof window === "undefined") {
      resolve(base64Str);
      return;
    }
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      let width = img.width;
      let height = img.height;

      if (width > height) {
        if (width > maxWidth) {
          height = Math.round((height * maxWidth) / width);
          width = maxWidth;
        }
      } else {
        if (height > maxHeight) {
          width = Math.round((width * maxHeight) / height);
          height = maxHeight;
        }
      }

      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(base64Str);
        return;
      }
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL("image/jpeg", 0.7));
    };
    img.onerror = () => {
      resolve(base64Str);
    };
    img.src = base64Str;
  });
};

const setCookie = (name, value, days) => {
  let expires = "";
  if (days) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    expires = "; expires=" + date.toUTCString();
  }
  if (typeof document !== "undefined") {
    const isSecure = window.location.protocol === "https:";
    document.cookie = name + "=" + (value || "") + expires + "; path=/; samesite=lax" + (isSecure ? "; secure" : "");
  }
};

const getCookie = (name) => {
  if (typeof document === "undefined") return null;
  const nameEQ = name + "=";
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) == ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
  }
  return null;
};

const eraseCookie = (name) => {
  if (typeof document !== "undefined") {
    document.cookie = name + '=; Max-Age=-99999999; path=/';
  }
};

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

// Global promise to prevent concurrent duplicate refresh requests
let refreshTokenPromise = null;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [avatar, setAvatar] = useState("");

  const refreshUser = async () => {
    const stored =
      localStorage.getItem("invexo_token") ||
      sessionStorage.getItem("invexo_token") ||
      getCookie("invexo_token");

    if (!stored) return null;

    const res = await API.get("/auth/me", {
      headers: { Authorization: `Bearer ${stored}` },
    });
    setUser(res.data);
    setToken(stored);
    return res.data;
  };

  const performTokenRefresh = async () => {
    if (refreshTokenPromise) {
      return refreshTokenPromise;
    }

    refreshTokenPromise = (async () => {
      try {
        const storedRefresh =
          localStorage.getItem("invexo_refresh_token") ||
          sessionStorage.getItem("invexo_refresh_token") ||
          getCookie("invexo_refresh_token");

        if (!storedRefresh) {
          throw new Error("No refresh token found");
        }

        const res = await API.post("/auth/refresh", { refresh_token: storedRefresh });
        const { access_token, refresh_token } = res.data;

        setToken(access_token);

        const rememberMe = !!localStorage.getItem("invexo_refresh_token");
        if (rememberMe) {
          localStorage.setItem("invexo_token", access_token);
          localStorage.setItem("invexo_refresh_token", refresh_token);
          setCookie("invexo_token", access_token, 30);
          setCookie("invexo_refresh_token", refresh_token, 30);
        } else {
          sessionStorage.setItem("invexo_token", access_token);
          sessionStorage.setItem("invexo_refresh_token", refresh_token);
          setCookie("invexo_token", access_token, null);
          setCookie("invexo_refresh_token", refresh_token, null);
        }

        return access_token;
      } catch (err) {
        // Clear both access and refresh tokens if rotation fails
        localStorage.removeItem("invexo_token");
        sessionStorage.removeItem("invexo_token");
        eraseCookie("invexo_token");
        localStorage.removeItem("invexo_refresh_token");
        sessionStorage.removeItem("invexo_refresh_token");
        eraseCookie("invexo_refresh_token");
        setToken(null);
        setUser(null);
        throw err;
      } finally {
        refreshTokenPromise = null;
      }
    })();

    return refreshTokenPromise;
  };

  // Register Axios response interceptor for 401 token refresh on mount
  useEffect(() => {
    const interceptor = API.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        if (
          error.response?.status === 401 &&
          !originalRequest._retry &&
          originalRequest.url &&
          !originalRequest.url.includes("/auth/login") &&
          !originalRequest.url.includes("/auth/signup") &&
          !originalRequest.url.includes("/auth/refresh")
        ) {
          originalRequest._retry = true;
          try {
            const freshToken = await performTokenRefresh();
            if (freshToken) {
              originalRequest.headers = originalRequest.headers || {};
              originalRequest.headers.Authorization = `Bearer ${freshToken}`;
              return API(originalRequest);
            }
          } catch (refreshError) {
            return Promise.reject(refreshError);
          }
        }
        return Promise.reject(error);
      }
    );

    return () => {
      API.interceptors.response.eject(interceptor);
    };
  }, []);

  // On mount, restore session from localStorage, sessionStorage, or cookie
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

    const stored =
      localStorage.getItem("invexo_token") ||
      sessionStorage.getItem("invexo_token") ||
      getCookie("invexo_token");

    if (!stored) {
      setLoading(false);
      return;
    }

    // Validate token with backend
    API.get("/auth/me", {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then((res) => {
        setUser(res.data);
        // Avoid overwriting the token if refreshed during mount
        const currentToken =
          localStorage.getItem("invexo_token") ||
          sessionStorage.getItem("invexo_token") ||
          getCookie("invexo_token");
        setToken(currentToken || stored);
      })
      .catch(() => {
        // Token invalid or expired; clear it
        localStorage.removeItem("invexo_token");
        sessionStorage.removeItem("invexo_token");
        eraseCookie("invexo_token");
        localStorage.removeItem("invexo_refresh_token");
        sessionStorage.removeItem("invexo_refresh_token");
        eraseCookie("invexo_refresh_token");
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password, rememberMe = false) => {
    const res = await API.post("/auth/login", { email, password });
    const { token, access_token, refresh_token, user: u } = res.data;
    const tk = token || access_token;
    setToken(tk);
    setUser(u);
    if (rememberMe) {
      localStorage.setItem("invexo_token", tk);
      localStorage.setItem("invexo_refresh_token", refresh_token);
      setCookie("invexo_token", tk, 30); // 30 days
      setCookie("invexo_refresh_token", refresh_token, 30);
    } else {
      sessionStorage.setItem("invexo_token", tk);
      sessionStorage.setItem("invexo_refresh_token", refresh_token);
      setCookie("invexo_token", tk, null); // session cookie
      setCookie("invexo_refresh_token", refresh_token, null);
    }
    return u;
  };

  const signup = async (email, password, name, age, rememberMe = false) => {
    const res = await API.post("/auth/signup", { email, password, name, age });
    const { token, access_token, refresh_token, user: u } = res.data;
    const tk = token || access_token;
    setToken(tk);
    setUser(u);
    if (rememberMe) {
      localStorage.setItem("invexo_token", tk);
      localStorage.setItem("invexo_refresh_token", refresh_token);
      setCookie("invexo_token", tk, 30);
      setCookie("invexo_refresh_token", refresh_token, 30);
    } else {
      sessionStorage.setItem("invexo_token", tk);
      sessionStorage.setItem("invexo_refresh_token", refresh_token);
      setCookie("invexo_token", tk, null);
      setCookie("invexo_refresh_token", refresh_token, null);
    }
    return u;
  };

  const initiateSignupOtp = async (email, password, name, age) => {
    const res = await API.post("/auth/signup/initiate", { email, password, name, age });
    return res.data;
  };

  const verifySignupOtp = async (email, otp, rememberMe = false) => {
    const res = await API.post("/auth/signup/verify", { email, otp });
    const { token, access_token, refresh_token, user: u } = res.data;
    const tk = token || access_token;
    setToken(tk);
    setUser(u);
    if (rememberMe) {
      localStorage.setItem("invexo_token", tk);
      localStorage.setItem("invexo_refresh_token", refresh_token);
      setCookie("invexo_token", tk, 30);
      setCookie("invexo_refresh_token", refresh_token, 30);
    } else {
      sessionStorage.setItem("invexo_token", tk);
      sessionStorage.setItem("invexo_refresh_token", refresh_token);
      setCookie("invexo_token", tk, null);
      setCookie("invexo_refresh_token", refresh_token, null);
    }
    return u;
  };

  const initiateForgotPassword = async (email) => {
    const res = await API.post("/auth/forgot-password/initiate", { email });
    return res.data;
  };

  const verifyForgotPasswordOtp = async (email, otp) => {
    const res = await API.post("/auth/forgot-password/verify-otp", { email, otp });
    return res.data;
  };

  const resetPassword = async (email, otp, new_password) => {
    const res = await API.post("/auth/forgot-password/reset", { email, otp, new_password });
    return res.data;
  };

  const logout = async () => {
    const storedRefresh =
      localStorage.getItem("invexo_refresh_token") ||
      sessionStorage.getItem("invexo_refresh_token") ||
      getCookie("invexo_refresh_token");

    if (storedRefresh) {
      try {
        await API.post("/auth/logout", { refresh_token: storedRefresh });
      } catch (err) {
        console.error("Backend logout error:", err);
      }
    }

    setUser(null);
    setToken(null);
    
    // Clear access tokens
    localStorage.removeItem("invexo_token");
    sessionStorage.removeItem("invexo_token");
    eraseCookie("invexo_token");
    
    // Clear refresh tokens
    localStorage.removeItem("invexo_refresh_token");
    sessionStorage.removeItem("invexo_refresh_token");
    eraseCookie("invexo_refresh_token");
    
    // Also clear old portfolio uid if present
    localStorage.removeItem("invexo_uid");
  };

  useEffect(() => {
    if (user?.id) {
      if (user.profile_photo) {
        setAvatar(user.profile_photo);
        localStorage.setItem(`invexo_profile_photo_${user.id}`, user.profile_photo);
      } else {
        const savedAvatar = localStorage.getItem(`invexo_profile_photo_${user.id}`) || localStorage.getItem("invexo_profile_photo");
        setAvatar(savedAvatar || "");
      }
    } else {
      setAvatar("");
    }
  }, [user]);

  const updateAvatar = async (data) => {
    if (!data) {
      setAvatar("");
      if (user?.id) {
        localStorage.removeItem(`invexo_profile_photo_${user.id}`);
        try {
          const res = await API.patch("/auth/profile", { profile_photo: "" });
          setUser(res.data);
        } catch (err) {
          console.error("Failed to clear profile photo on backend:", err);
        }
      }
      localStorage.removeItem("invexo_profile_photo");
      return;
    }

    try {
      const compressed = await resizeImage(data);
      setAvatar(compressed);
      if (user?.id) {
        localStorage.setItem(`invexo_profile_photo_${user.id}`, compressed);
        const res = await API.patch("/auth/profile", { profile_photo: compressed });
        setUser(res.data);
      }
      localStorage.setItem("invexo_profile_photo", compressed);
    } catch (err) {
      console.error("Failed to sync profile photo to backend:", err);
      setAvatar(data);
    }
  };

  return (
    <AuthContext.Provider
      value={{ 
        user, token, loading, 
        login, signup, initiateSignupOtp, verifySignupOtp, 
        initiateForgotPassword, verifyForgotPasswordOtp, resetPassword,
        logout, refreshUser, setUser,
        refreshAccessToken: performTokenRefresh,
        avatar, updateAvatar
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
