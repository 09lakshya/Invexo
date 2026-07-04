import { useEffect, useState, useRef } from "react";
import Head from "next/head";
import Navbar from "../components/Navbar";
import API from "../services/api";
import Icon from "../components/Icon";

export default function GeneralNewsPage() {
  const [news, setNews] = useState([]);
  const [dailyNews, setDailyNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);

  // Suggestions states
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionIndex, setSuggestionIndex] = useState(-1);

  const [placeholder, setPlaceholder] = useState("Search topics, companies, or keywords...");

  const searchContainerRef = useRef(null);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 600) {
        setPlaceholder("Search news...");
      } else {
        setPlaceholder("Search topics, companies, or keywords...");
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Initial fetch
  useEffect(() => {
    const fetchNews = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await API.get("/news/general");
        const articles = Array.isArray(res.data) ? res.data : [];
        setNews(articles);
        setDailyNews(articles);
      } catch (err) {
        console.error("Error fetching general news:", err);
        setError("Failed to load news. Please try again later.");
      } finally {
        setLoading(false);
      }
    };
    fetchNews();
  }, []);

  // Debounced suggestions fetch
  useEffect(() => {
    const query = searchQuery.trim();
    if (query.length < 3) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const delayDebounceFn = setTimeout(async () => {
      try {
        const res = await API.get(`/news/general/suggest?q=${encodeURIComponent(query)}`);
        setSuggestions(Array.isArray(res.data) ? res.data : []);
        setShowSuggestions(true);
        setSuggestionIndex(-1);
      } catch (err) {
        console.error("Error fetching suggestions:", err);
      }
    }, 250);

    return () => clearTimeout(delayDebounceFn);
  }, [searchQuery]);

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const executeSearch = async (query) => {
    try {
      setSearching(true);
      setError(null);
      setActiveQuery(query);
      const res = await API.get(`/news/general/search?q=${encodeURIComponent(query)}`);
      setNews(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error("Error searching news:", err);
      setError("Failed to search news. Please try again later.");
    } finally {
      setSearching(false);
    }
  };

  const handleSearch = (e) => {
    if (e) e.preventDefault();
    const query = searchQuery.trim();
    if (!query) {
      handleClearSearch();
      return;
    }
    setShowSuggestions(false);
    executeSearch(query);
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    setActiveQuery("");
    setNews(dailyNews);
    setSuggestions([]);
    setShowSuggestions(false);
    setError(null);
  };

  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSuggestionIndex((prevIndex) =>
        prevIndex < suggestions.length - 1 ? prevIndex + 1 : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSuggestionIndex((prevIndex) =>
        prevIndex > 0 ? prevIndex - 1 : suggestions.length - 1
      );
    } else if (e.key === "Enter") {
      if (suggestionIndex >= 0 && suggestionIndex < suggestions.length) {
        e.preventDefault();
        const selected = suggestions[suggestionIndex].title;
        setSearchQuery(selected);
        setShowSuggestions(false);
        executeSearch(selected);
      } else {
        handleSearch(e);
      }
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  return (
    <>
      <Head>
        <title>Invexo — Live Business News & Current Affairs</title>
        <meta name="description" content="Read the latest business news, markets updates, and current affairs summarized by Invexo AI." />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />

        <div style={{ maxWidth: "900px", margin: "0 auto", padding: "clamp(20px, 4vmin, 32px) clamp(12px, 3vmin, 24px) clamp(40px, 8vmin, 64px)" }}>
          
          {/* Header */}
          <div style={{ marginBottom: "32px", animation: "fadeInUp 0.5s ease both" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", margin: 0 }}>
                  {activeQuery ? "Search Results" : "Daily Feed"}
                </p>
                {activeQuery && (
                  <button
                    onClick={handleClearSearch}
                    style={{
                      background: "var(--accent-dim)",
                      border: "1px solid var(--accent-glow)",
                      borderRadius: "6px",
                      color: "var(--accent)",
                      fontSize: "0.68rem",
                      fontWeight: 700,
                      cursor: "pointer",
                      padding: "2px 8px",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                      transition: "opacity 0.2s"
                    }}
                    onMouseEnter={e => e.currentTarget.style.opacity = 0.8}
                    onMouseLeave={e => e.currentTarget.style.opacity = 1}
                  >
                    &larr; Reset Feed
                  </button>
                )}
              </div>
              {!loading && !searching && news.length > 0 && (
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0, fontWeight: 500 }}>
                  {news.length} {news.length === 1 ? "article" : "articles"} available
                </p>
              )}
            </div>
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "clamp(2rem, 4vmin, 3rem)",
              fontWeight: 800,
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
              background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
              margin: "0 0 10px 0"
            }}>
              {activeQuery ? `"${activeQuery}"` : "Business & Affairs"}
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", margin: 0 }}>
              {activeQuery
                ? `Showing matching archived and live news reports for "${activeQuery}".`
                : "Curated daily summaries of key market events, corporate updates, and economic affairs."}
            </p>
          </div>

          <style>{`
            @media (max-width: 600px) {
              .search-submit-button {
                padding: 10px !important;
                border-radius: 12px !important;
              }
              .search-btn-text {
                display: none !important;
              }
            }
          `}</style>

          {/* Search Bar Container */}
          <div ref={searchContainerRef} style={{ position: "relative", marginBottom: "32px", zIndex: 50 }}>
            <form
              onSubmit={handleSearch}
              style={{
                display: "flex",
                gap: "12px",
                background: "var(--bg-card)",
                border: searchFocused ? "1px solid var(--accent-glow)" : "1px solid var(--border-subtle)",
                borderRadius: "16px",
                padding: "6px 6px 6px 16px",
                boxShadow: searchFocused ? "0 8px 30px var(--shadow-card), 0 0 1px var(--accent-glow)" : "var(--shadow-card)",
                backdropFilter: "blur(16px)",
                alignItems: "center",
                transition: "all 0.25s ease"
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: "4px", flexShrink: 0 }}>
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input
                type="text"
                placeholder={placeholder}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => {
                  setSearchFocused(true);
                  if (suggestions.length > 0) setShowSuggestions(true);
                }}
                onBlur={() => setSearchFocused(false)}
                onKeyDown={handleKeyDown}
                style={{
                  flex: 1,
                  minWidth: 0,
                  background: "transparent",
                  border: "none",
                  color: "var(--text-primary)",
                  fontSize: "0.95rem",
                  outline: "none",
                  padding: "8px 0"
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={handleClearSearch}
                  style={{
                    flexShrink: 0,
                    background: "transparent",
                    border: "none",
                    color: "var(--text-muted)",
                    cursor: "pointer",
                    padding: "4px 8px",
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    transition: "color 0.2s"
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = "var(--text-primary)"}
                  onMouseLeave={e => e.currentTarget.style.color = "var(--text-muted)"}
                >
                  Clear
                </button>
              )}
              <button
                type="submit"
                disabled={searching}
                className="search-submit-button"
                style={{
                  flexShrink: 0,
                  background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
                  border: "none",
                  color: "var(--bg-primary)",
                  padding: "10px 20px",
                  borderRadius: "12px",
                  fontWeight: 600,
                  fontSize: "0.9rem",
                  cursor: "pointer",
                  transition: "opacity 0.2s",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
                onMouseEnter={e => e.currentTarget.style.opacity = 0.9}
                onMouseLeave={e => e.currentTarget.style.opacity = 1}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                  <circle cx="11" cy="11" r="8"></circle>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <span className="search-btn-text">
                  {searching ? "Searching..." : "Search"}
                </span>
              </button>
            </form>

            {/* Suggestions Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  right: 0,
                  zIndex: 100,
                  marginTop: "8px",
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "16px",
                  boxShadow: "0 12px 40px rgba(0, 0, 0, 0.4), 0 0 1px var(--border-subtle)",
                  backdropFilter: "blur(20px)",
                  overflow: "hidden",
                  padding: "8px 0",
                  animation: "fadeInUp 0.15s ease both"
                }}
              >
                {suggestions.map((item, idx) => {
                  const isSelected = idx === suggestionIndex;
                  return (
                    <div
                      key={idx}
                      onClick={() => {
                        setSearchQuery(item.title);
                        setShowSuggestions(false);
                        executeSearch(item.title);
                      }}
                      onMouseEnter={() => setSuggestionIndex(idx)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "12px 18px",
                        cursor: "pointer",
                        background: isSelected ? "var(--accent-dim)" : "transparent",
                        transition: "all 0.15s ease",
                        borderLeft: isSelected ? "3px solid var(--accent)" : "3px solid transparent",
                        textAlign: "left"
                      }}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke={isSelected ? "var(--accent)" : "var(--text-muted)"}
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{ flexShrink: 0, transition: "stroke 0.15s ease" }}
                      >
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                      </svg>
                      <span
                        style={{
                          fontSize: "0.9rem",
                          fontWeight: isSelected ? 600 : 400,
                          color: isSelected ? "var(--accent)" : "var(--text-primary)",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          transition: "color 0.15s ease"
                        }}
                      >
                        {item.title}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* News list */}
          {loading || searching ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {Array.from({ length: 4 }).map((_, idx) => (
                <div key={idx} style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "20px",
                  padding: "28px",
                  height: "180px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "14px"
                }}>
                  <div className="skeleton" style={{ width: "20%", height: "12px" }} />
                  <div className="skeleton" style={{ width: "70%", height: "24px" }} />
                  <div className="skeleton" style={{ width: "95%", height: "14px" }} />
                  <div className="skeleton" style={{ width: "80%", height: "14px" }} />
                </div>
              ))}
            </div>
          ) : error ? (
            <div style={{
              background: "var(--bg-card)",
              border: "1px solid var(--red-dim)",
              borderRadius: "20px",
              padding: "60px 24px",
              textAlign: "center",
              boxShadow: "var(--shadow-card)",
            }}>
              <p style={{ marginBottom: "16px", color: "var(--red)", display: "flex", justifyContent: "center" }}><Icon name="alert" size={44} strokeWidth={1.5} /></p>
              <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "1.3rem", color: "var(--text-primary)", marginBottom: "8px" }}>
                {error}
              </h2>
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                Could not connect to the news server. Please make sure the backend is active.
              </p>
            </div>
          ) : news.length === 0 ? (
            <div style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "20px",
              padding: "60px 24px",
              textAlign: "center",
              boxShadow: "var(--shadow-card)",
            }}>
              <p style={{ marginBottom: "16px", color: "var(--text-muted)", display: "flex", justifyContent: "center" }}><Icon name="search" size={44} strokeWidth={1.5} /></p>
              <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "1.3rem", color: "var(--text-primary)", marginBottom: "8px" }}>
                {activeQuery ? `No Results for "${activeQuery}"` : "No News Available"}
              </h2>
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: activeQuery ? "20px" : "0" }}>
                {activeQuery
                  ? "We couldn't find any articles matching your search. Try adjusting your keywords or return to the main feed."
                  : "We couldn't fetch any news articles for today. Please check back later."}
              </p>
              {activeQuery && (
                <button
                  onClick={handleClearSearch}
                  style={{
                    background: "var(--accent-dim)",
                    border: "1px solid var(--accent-glow)",
                    color: "var(--accent)",
                    padding: "10px 20px",
                    borderRadius: "12px",
                    fontWeight: 600,
                    fontSize: "0.9rem",
                    cursor: "pointer",
                    transition: "all 0.2s"
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = "var(--accent)";
                    e.currentTarget.style.color = "var(--bg-primary)";
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = "var(--accent-dim)";
                    e.currentTarget.style.color = "var(--accent)";
                  }}
                >
                  Return to Daily Feed
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {news.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "20px",
                    padding: "28px",
                    boxShadow: "var(--shadow-card)",
                    backdropFilter: "blur(16px)",
                    transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                    animation: `fadeInUp 0.5s ${idx * 0.08}s ease both`,
                    position: "relative",
                    overflow: "hidden"
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = "var(--accent-glow)";
                    e.currentTarget.style.transform = "translateY(-4px)";
                    e.currentTarget.style.boxShadow = "0 8px 30px var(--shadow-card), 0 0 1px var(--accent-glow)";
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = "var(--border-subtle)";
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = "var(--shadow-card)";
                  }}
                >
                  {/* Accent glow line */}
                  <div style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "3px",
                    background: "linear-gradient(90deg, var(--accent) 0%, transparent 100%)",
                    opacity: 0.6
                  }} />

                  {/* Date and Category Tag */}
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
                    <span style={{
                      fontSize: "0.68rem",
                      fontWeight: 800,
                      color: "var(--accent)",
                      background: "var(--accent-dim)",
                      padding: "3px 10px",
                      borderRadius: "6px",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      border: "1px solid var(--accent-glow)"
                    }}>
                      Business
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 500 }}>
                      {item.date}
                    </span>
                  </div>

                  {/* Heading */}
                  <h2 style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "clamp(1.1rem, 2.5vmin, 1.3rem)",
                    fontWeight: 800,
                    color: "var(--text-primary)",
                    margin: "0 0 14px 0",
                    lineHeight: 1.3,
                    letterSpacing: "-0.01em"
                  }}>
                    {item.title}
                  </h2>

                  {/* Entire News (60-100 words) */}
                  <p style={{
                    color: "var(--text-secondary)",
                    fontSize: "0.9rem",
                    lineHeight: 1.6,
                    margin: "0 0 18px 0",
                    fontWeight: 400
                  }}>
                    {item.summary}
                  </p>

                  {/* Link to Read More */}
                  {item.link && item.link !== "#" && (
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        color: "var(--accent)",
                        fontSize: "0.82rem",
                        fontWeight: 700,
                        textDecoration: "none",
                        transition: "opacity 0.2s"
                      }}
                      onMouseEnter={e => e.currentTarget.style.opacity = 0.8}
                      onMouseLeave={e => e.currentTarget.style.opacity = 1}
                    >
                      Read original article &rarr;
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

        </div>
      </div>
    </>
  );
}
