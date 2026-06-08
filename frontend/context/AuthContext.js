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

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    const stored =
      localStorage.getItem("ntrade_token") ||
      sessionStorage.getItem("ntrade_token");

    if (!stored) return null;

    const res = await API.get("/auth/me", {
      headers: { Authorization: `Bearer ${stored}` },
    });
    setUser(res.data);
    setToken(stored);
    return res.data;
  };

  // On mount, restore session from localStorage or sessionStorage
  useEffect(() => {
    const stored =
      localStorage.getItem("ntrade_token") ||
      sessionStorage.getItem("ntrade_token");

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
        setToken(stored);
      })
      .catch(() => {
        // Token invalid or expired; clear it
        localStorage.removeItem("ntrade_token");
        sessionStorage.removeItem("ntrade_token");
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password, rememberMe = false) => {
    const res = await API.post("/auth/login", { email, password });
    const { token: tk, user: u } = res.data;
    setToken(tk);
    setUser(u);
    if (rememberMe) {
      localStorage.setItem("ntrade_token", tk);
    } else {
      sessionStorage.setItem("ntrade_token", tk);
    }
    return u;
  };

  const signup = async (email, password, name, age, rememberMe = false) => {
    const res = await API.post("/auth/signup", { email, password, name, age });
    const { token: tk, user: u } = res.data;
    setToken(tk);
    setUser(u);
    if (rememberMe) {
      localStorage.setItem("ntrade_token", tk);
    } else {
      sessionStorage.setItem("ntrade_token", tk);
    }
    return u;
  };

  const initiateSignupOtp = async (email, password, name, age) => {
    const res = await API.post("/auth/signup/initiate", { email, password, name, age });
    return res.data;
  };

  const verifySignupOtp = async (email, otp, rememberMe = false) => {
    const res = await API.post("/auth/signup/verify", { email, otp });
    const { token: tk, user: u } = res.data;
    setToken(tk);
    setUser(u);
    if (rememberMe) {
      localStorage.setItem("ntrade_token", tk);
    } else {
      sessionStorage.setItem("ntrade_token", tk);
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

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("ntrade_token");
    sessionStorage.removeItem("ntrade_token");
    // Also clear old portfolio uid if present
    localStorage.removeItem("ntrade_uid");
  };

  const [avatar, setAvatar] = useState("");

  useEffect(() => {
    if (user?.id) {
      if (user.profile_photo) {
        setAvatar(user.profile_photo);
        localStorage.setItem(`ntrade_profile_photo_${user.id}`, user.profile_photo);
      } else {
        const savedAvatar = localStorage.getItem(`ntrade_profile_photo_${user.id}`) || localStorage.getItem("ntrade_profile_photo");
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
        localStorage.removeItem(`ntrade_profile_photo_${user.id}`);
        try {
          const res = await API.patch("/auth/profile", { profile_photo: "" });
          setUser(res.data);
        } catch (err) {
          console.error("Failed to clear profile photo on backend:", err);
        }
      }
      localStorage.removeItem("ntrade_profile_photo");
      return;
    }

    try {
      const compressed = await resizeImage(data);
      setAvatar(compressed);
      if (user?.id) {
        localStorage.setItem(`ntrade_profile_photo_${user.id}`, compressed);
        const res = await API.patch("/auth/profile", { profile_photo: compressed });
        setUser(res.data);
      }
      localStorage.setItem("ntrade_profile_photo", compressed);
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
        avatar, updateAvatar 
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
