import { QuoteView } from "@/components/quote-view";

export default async function Page({ params }: PageProps<"/[locale]/quote/[quoteId]">) {
  const { quoteId } = await params;
  return <QuoteView quoteId={quoteId} />;
}
