import { Database } from 'lucide-react';
import type { EvidenceNode, InvestigationResult } from '../../types';
import { Card, PanelTitle } from '../ui';

const NODE_ICON: Record<string, string> = {
  PAYMENT_RECORD: '💳',
  ORDER_RECORD: '📋',
  INVOICE: '🧾',
  SHIPPING_PROOF: '📦',
  DELIVERY_CONFIRMATION: '✅',
  CUSTOMER_COMMUNICATION: '💬',
  REFUND_CONFIRMATION: '💰',
  REFUND_POLICY: '📜',
  PRODUCT_DESCRIPTION: '🏷️',
  PRODUCT_SPECIFICATION: '⚙️',
  CANCELLATION_POLICY: '🚫',
};

function NodeButton({
  node,
  selected,
  highlighted,
  onClick,
  compact,
}: {
  node: EvidenceNode;
  selected: boolean;
  highlighted: boolean;
  onClick: () => void;
  compact?: boolean;
}) {
  const base = selected
    ? 'bg-press/[.08] border-press text-press ring-1 ring-press'
    : highlighted
    ? 'bg-press/[.08]/60 border-press text-press'
    : 'bg-paper border-paper-rule text-graphite-500 hover:border-graphite-400 hover:text-graphite-900';
  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      className={` font-bold font-mono border transition ${base} ${
 compact ? 'px-2.5 py-1.5 text-2xs' : 'px-3 py-1.5 text-2xs'
      }`}
    >
      {NODE_ICON[node.type] || '📄'} {node.type.replace(/_/g, ' ')}
    </button>
  );
}

export default function EvidenceGraphPanel({
  investigation,
  amount,
  selectedNode,
  onSelectNode,
  highlightedEvidenceId,
}: {
  investigation: InvestigationResult;
  amount?: number;
  selectedNode: string | null;
  onSelectNode: (id: string | null) => void;
  highlightedEvidenceId: string | null;
}) {
  const nodes = investigation.evidence_graph.nodes;
  const payment = nodes.filter((n) => n.type === 'PAYMENT_RECORD');
  const order = nodes.filter((n) => n.type === 'ORDER_RECORD');
  const rest = nodes.filter((n) => !['PAYMENT_RECORD', 'ORDER_RECORD'].includes(n.type));
  const inspected = nodes.find((n) => n.evidence_id === selectedNode);

  const toggle = (id: string) => onSelectNode(selectedNode === id ? null : id);

  return (
    <Card className="p-5 space-y-4">
      <PanelTitle
        icon={<Database className="w-4 h-4 text-press" />}
        right={<span className="text-2xs text-graphite-500 hidden sm:inline">Click any node to inspect</span>}
      >
        Evidence graph ({nodes.length} records)
      </PanelTitle>

      <div className="flex flex-col items-center gap-0 py-2">
        <div className="bg-paper border-2 border-press px-4 py-2 text-xs font-bold text-press font-mono text-center">
          DISPUTE {amount != null ? `₹${amount.toLocaleString('en-IN')}` : ''}
        </div>

        {payment.length > 0 && <div className="w-px h-4 bg-paper-sunk" />}
        <div className="flex items-center gap-6 flex-wrap justify-center">
          {payment.map((n) => (
            <NodeButton
              key={n.evidence_id}
              node={n}
              selected={selectedNode === n.evidence_id}
              highlighted={highlightedEvidenceId === n.evidence_id}
              onClick={() => toggle(n.evidence_id)}
            />
          ))}
        </div>

        {order.length > 0 && <div className="w-px h-3 bg-paper-sunk" />}
        <div className="flex items-center gap-6 flex-wrap justify-center">
          {order.map((n) => (
            <NodeButton
              key={n.evidence_id}
              node={n}
              selected={selectedNode === n.evidence_id}
              highlighted={highlightedEvidenceId === n.evidence_id}
              onClick={() => toggle(n.evidence_id)}
            />
          ))}
        </div>

        {rest.length > 0 && <div className="w-px h-3 bg-paper-sunk" />}
        <div className="flex items-start gap-2 flex-wrap justify-center">
          {rest.map((n) => (
            <NodeButton
              key={n.evidence_id}
              node={n}
              compact
              selected={selectedNode === n.evidence_id}
              highlighted={highlightedEvidenceId === n.evidence_id}
              onClick={() => toggle(n.evidence_id)}
            />
          ))}
        </div>
      </div>

      {inspected && (
        <div className="bg-paper border border-press/40 p-4 text-xs space-y-2">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="font-mono font-bold text-press break-all">{inspected.evidence_id}</span>
            <span className="text-2xs px-2 py-0.5 rounded bg-press/[.08] text-press font-mono border border-press/25">
              {inspected.type}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-2xs">
            <div>
              <span className="text-graphite-400">Source:</span> <span className="text-graphite-900">{inspected.source}</span>
            </div>
            <div>
              <span className="text-graphite-400">Reliability:</span>{' '}
              <span className="text-gain font-bold">{(inspected.reliability * 100).toFixed(0)}%</span>
            </div>
            <div>
              <span className="text-graphite-400">Supports:</span> <span className="text-graphite-900">{inspected.supports}</span>
            </div>
            <div>
              <span className="text-graphite-400">Razorpay field:</span>{' '}
              <span className="text-graphite-900 font-mono">{inspected.razorpay_field}</span>
            </div>
            {inspected.timestamp && (
              <div className="sm:col-span-2">
                <span className="text-graphite-400">Timestamp:</span>{' '}
                <span className="text-graphite-900 font-mono">{inspected.timestamp}</span>
              </div>
            )}
          </div>
          {inspected.content && (
            <div className="border-t border-paper-rule pt-2 space-y-1">
              {Object.entries(inspected.content)
                .filter(([, v]) => v != null)
                .map(([k, v]) => (
                  <div key={k} className="text-2xs break-words">
                    <span className="text-graphite-400">{k}:</span>{' '}
                    <span className="text-graphite-900 font-mono">{String(v)}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
