"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { requestCallback } from "@/lib/api";
import { useApiError } from "@/lib/use-api-error";

const HOURS = 4; // mirrors ASSISTED_CALLBACK_HOURS in api/app/config.py

export function HandoffDialog({ sessionId, open, onOpenChange }: { sessionId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const t = useTranslations("advisor");
  const errText = useApiError();
  const [phone, setPhone] = useState("");
  const [when, setWhen] = useState("anytime");
  const [busy, setBusy] = useState(false);
  const valid = /^[6-9]\d{9}$/.test(phone);

  async function submit() {
    setBusy(true);
    try {
      await requestCallback(sessionId, phone, when);
      toast.success(t("thanks", { hours: HOURS }));
      onOpenChange(false);
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("handoffTitle")}</DialogTitle>
          <DialogDescription>{t("handoffDesc", { hours: HOURS })}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            {t("phone")}
            <Input
              inputMode="numeric"
              autoComplete="tel-national"
              maxLength={10}
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
              className="h-11 text-base"
            />
          </label>
          <fieldset className="flex flex-col gap-1 text-sm">
            <legend className="mb-1">{t("time")}</legend>
            <div className="flex gap-2">
              {(["morning", "evening", "anytime"] as const).map((k) => (
                <Button key={k} type="button" variant={when === k ? "default" : "outline"} className="h-11 flex-1" onClick={() => setWhen(k)}>
                  {t(k)}
                </Button>
              ))}
            </div>
          </fieldset>
          <Button className="h-12 text-base" disabled={!valid || busy} onClick={submit}>
            {t("submit")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
