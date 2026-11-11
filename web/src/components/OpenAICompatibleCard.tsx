import { useState, type FormEvent } from "react";
import { Badge, Card, CardHead } from "./primitives";
import {
  useAddOpenAICompatibleConfig,
  useDeleteOpenAICompatibleConfig,
  useOpenAICompatibleConfigs,
  useOpenAICompatibleModels,
  useSetOpenAICompatibleModel,
  type OpenAICompatibleConfig,
} from "../lib/queries";
import type { useT } from "../lib/i18n";

export function OpenAICompatibleCard({
  siteId,
  t,
}: {
  siteId: string;
  t: ReturnType<typeof useT>;
}) {
  const configs = useOpenAICompatibleConfigs(siteId);
  const add = useAddOpenAICompatibleConfig(siteId);
  const remove = useDeleteOpenAICompatibleConfig(siteId);
  const setModel = useSetOpenAICompatibleModel(siteId);
  const [name, setName] = useState("");
  const [apiType, setApiType] = useState<
    "openai_compatible" | "openai_images" | "openai_responses"
  >("openai_compatible");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelId, setModelId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !baseUrl.trim() || apiKey.trim().length < 8) return;
    setBusy(true);
    setError(null);
    try {
      await add.mutateAsync({
        name: name.trim(),
        api_type: apiType,
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
        model_id: modelId.trim() || null,
      });
      setName("");
      setBaseUrl("");
      setApiKey("");
      setModelId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the connection");
    } finally {
      setBusy(false);
    }
  };

  const configRows = configs.data ?? [];

  return (
    <Card id="openai-compatible-providers">
      <CardHead
        icon="spark"
        title={t("providers.compatible_title", "Add OpenAI Compatible")}
        subtitle={t(
          "providers.compatible_subtitle",
          "Connect OpenRouter or any OpenAI-compatible gateway. Models are imported from its /models endpoint.",
        )}
      />
      <form onSubmit={onSubmit} style={formGridStyle}>
        <label className="field">
          <span>{t("providers.compatible_name", "Connection name")}</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="OpenRouter" />
        </label>
        <label className="field">
          <span>{t("providers.compatible_api_type", "API Type")}</span>
          <select className="input" value={apiType} onChange={(e) => setApiType(e.target.value as typeof apiType)}>
            <option value="openai_compatible">Chat Completions (OpenAI-compatible)</option>
            <option value="openai_images">OpenAI Images (/images/*)</option>
            <option value="openai_responses">OpenAI Responses (/responses)</option>
          </select>
        </label>
        <label className="field" style={{ gridColumn: "1 / -1" }}>
          <span>{t("providers.compatible_base_url", "Base URL")}</span>
          <input className="input" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.example.com/v1" />
        </label>
        <label className="field">
          <span>{t("providers.compatible_api_key", "API Key")}</span>
          <input className="input" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-…" autoComplete="new-password" />
        </label>
        <label className="field">
          <span>{t("providers.compatible_model_id", "Model ID (optional)")}</span>
          <input className="input" value={modelId} onChange={(e) => setModelId(e.target.value)} placeholder="Imported model ID" />
        </label>
        <div style={{ display: "flex", alignItems: "end", gap: 8 }}>
          <button className="btn btn-secondary" type="submit" disabled={busy || !name.trim() || !baseUrl.trim() || apiKey.trim().length < 8}>
            {busy ? "…" : t("providers.compatible_add", "Add connection")}
          </button>
        </div>
        {error ? <div className="caption" style={{ color: "var(--danger)", gridColumn: "1 / -1" }}>{error}</div> : null}
      </form>
      <div style={{ padding: "0 20px 20px" }}>
        {configs.isLoading ? <div className="caption">{t("providers.compatible_loading", "Loading connections…")}</div> : null}
        {!configs.isLoading && configRows.length === 0 ? (
          <div className="caption" style={{ color: "var(--text-subtle)" }}>
            {t("providers.compatible_empty", "No OpenAI-compatible connections have been added.")}
          </div>
        ) : null}
        {configRows.map((config) => (
          <CompatibleConfigRow
            key={config.id}
            siteId={siteId}
            config={config}
            t={t}
            onDelete={async () => {
              if (window.confirm(t("providers.compatible_confirm_remove", "Remove this connection?"))) {
                await remove.mutateAsync(config.id);
              }
            }}
            onSetModel={(modelId) => setModel.mutateAsync({ configId: config.id, modelId })}
          />
        ))}
      </div>
    </Card>
  );
}

function CompatibleConfigRow({
  siteId,
  config,
  t,
  onDelete,
  onSetModel,
}: {
  siteId: string;
  config: OpenAICompatibleConfig;
  t: ReturnType<typeof useT>;
  onDelete: () => Promise<void>;
  onSetModel: (modelId: string | null) => Promise<unknown>;
}) {
  const models = useOpenAICompatibleModels(siteId, config.id);
  const availableModels = models.data ?? [];
  const imageModels = availableModels.filter((model) => model.supports_image_output);
  const [selected, setSelected] = useState(config.model_id ?? "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await onSetModel(selected || null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={connectionRowStyle}>
      <div style={{ minWidth: 190, flex: "1 1 220px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <strong>{config.name}</strong>
          <Badge variant="success">{config.api_type}</Badge>
        </div>
        <div className="caption" style={{ marginTop: 4, wordBreak: "break-all" }}>{config.base_url}</div>
      </div>
      <div style={connectionControlsStyle}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void models.refetch()} disabled={models.isFetching}>
          {models.isFetching ? "…" : t("providers.compatible_import", "Import models")}
        </button>
        <select className="input" value={selected} onChange={(e) => setSelected(e.target.value)} style={{ minWidth: 220 }}>
          <option value="">{t("providers.compatible_select_image", "Select image model")}</option>
          {availableModels.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name || model.id}{model.supports_image_output ? " · image" : ""}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => void save()} disabled={saving || !selected || selected === config.model_id}>
          {saving ? "…" : t("providers.compatible_set_model", "Set model")}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onDelete()} style={{ color: "var(--danger)" }}>
          {t("providers.remove", "Remove")}
        </button>
      </div>
      {models.isError ? <div className="caption" style={{ color: "var(--warning)", flexBasis: "100%" }}>{t("providers.compatible_import_failed", "Could not import models from this Base URL.")}</div> : null}
      {!models.isLoading && !models.isError && models.data && imageModels.length === 0 ? <div className="caption" style={{ color: "var(--warning)", flexBasis: "100%" }}>{t("providers.compatible_no_image_models", "No image-capable models were advertised by this provider.")}</div> : null}
    </div>
  );
}

const formGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: 12,
  padding: "4px 20px 18px",
};

const connectionRowStyle = {
  display: "flex",
  gap: 12,
  alignItems: "center",
  flexWrap: "wrap" as const,
  padding: "14px 0",
  borderTop: "1px solid var(--border)",
};

const connectionControlsStyle = {
  display: "flex",
  gap: 8,
  alignItems: "center",
  flexWrap: "wrap" as const,
  justifyContent: "flex-end",
};
