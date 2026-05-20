import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles/globals.css";

const qc = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 10_000 },
  },
});

const root = document.getElementById("app");
if (!root) throw new Error("#app not found");

const basename = window.location.pathname.startsWith("/dashboard") ? "/dashboard" : "/";

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter basename={basename}>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
