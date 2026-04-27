import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = "/api/v1";

function formatPaise(paise) {
  return `₹${(paise / 100).toFixed(2)}`;
}

function Badge({ status }) {
  const colors = {
    pending: "bg-yellow-100 text-yellow-800",
    processing: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || "bg-gray-100"}`}>
      {status}
    </span>
  );
}

function MerchantCard({ merchant, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border cursor-pointer transition-all ${
        selected ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-blue-300"
      }`}
    >
      <h3 className="font-semibold text-gray-800">{merchant.name}</h3>
      <p className="text-sm text-gray-500">{merchant.email}</p>
      <div className="mt-2 flex gap-4">
        <div>
          <p className="text-xs text-gray-400">Available</p>
          <p className="font-bold text-green-600">{formatPaise(merchant.available_balance_paise)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Held</p>
          <p className="font-bold text-yellow-600">{formatPaise(merchant.held_balance_paise)}</p>
        </div>
      </div>
    </div>
  );
}

function PayoutForm({ merchant, onSuccess }) {
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [bankAccounts, setBankAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    axios.get(`${API}/merchants/${merchant.id}/bank-accounts/`)
      .then(res => {
        setBankAccounts(res.data);
        if (res.data.length > 0) setBankAccountId(res.data[0].id);
      });
  }, [merchant.id]);

  const handleSubmit = async () => {
    setError("");
    if (!amount || isNaN(amount) || Number(amount) <= 0) {
      setError("Enter a valid amount in rupees.");
      return;
    }
    const amountPaise = Math.round(Number(amount) * 100);
    const idempotencyKey = crypto.randomUUID();
    setLoading(true);
    try {
      await axios.post(
        `${API}/merchants/${merchant.id}/payouts/create/`,
        { amount_paise: amountPaise, bank_account_id: Number(bankAccountId) },
        { headers: { "Idempotency-Key": idempotencyKey } }
      );
      setAmount("");
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.error || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-800 mb-3">Request Payout</h3>
      <div className="flex gap-2 flex-wrap">
        <input
          type="number"
          placeholder="Amount in ₹"
          value={amount}
          onChange={e => setAmount(e.target.value)}
          className="border rounded px-3 py-2 text-sm flex-1 min-w-32"
        />
        <select
          value={bankAccountId}
          onChange={e => setBankAccountId(e.target.value)}
          className="border rounded px-3 py-2 text-sm flex-1 min-w-40"
        >
          {bankAccounts.map(acc => (
            <option key={acc.id} value={acc.id}>
              {acc.account_holder_name} - {acc.account_number}
            </option>
          ))}
        </select>
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Requesting..." : "Request Payout"}
        </button>
      </div>
      {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
    </div>
  );
}

function PayoutsTable({ merchantId, refresh }) {
  const [payouts, setPayouts] = useState([]);

  const fetchPayouts = useCallback(() => {
    axios.get(`${API}/merchants/${merchantId}/payouts/`)
      .then(res => setPayouts(res.data));
  }, [merchantId]);

  useEffect(() => {
    fetchPayouts();
    const interval = setInterval(fetchPayouts, 3000);
    return () => clearInterval(interval);
  }, [fetchPayouts, refresh]);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-800 mb-3">Payout History</h3>
      {payouts.length === 0 ? (
        <p className="text-gray-400 text-sm">No payouts yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b">
              <th className="pb-2">ID</th>
              <th className="pb-2">Amount</th>
              <th className="pb-2">Status</th>
              <th className="pb-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {payouts.map(p => (
              <tr key={p.id} className="border-b last:border-0">
                <td className="py-2 text-gray-500">#{p.id}</td>
                <td className="py-2 font-medium">{formatPaise(p.amount_paise)}</td>
                <td className="py-2"><Badge status={p.status} /></td>
                <td className="py-2 text-gray-400">
                  {new Date(p.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function LedgerTable({ merchantId }) {
  const [entries, setEntries] = useState([]);

  useEffect(() => {
    axios.get(`${API}/merchants/${merchantId}/ledger/`)
      .then(res => setEntries(res.data));
  }, [merchantId]);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-800 mb-3">Ledger</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-400 border-b">
            <th className="pb-2">Type</th>
            <th className="pb-2">Amount</th>
            <th className="pb-2">Description</th>
            <th className="pb-2">Date</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(e => (
            <tr key={e.id} className="border-b last:border-0">
              <td className="py-2">
                <span className={`font-medium ${e.entry_type === 'credit' ? 'text-green-600' : 'text-red-600'}`}>
                  {e.entry_type}
                </span>
              </td>
              <td className="py-2">{formatPaise(e.amount_paise)}</td>
              <td className="py-2 text-gray-500">{e.description}</td>
              <td className="py-2 text-gray-400">
                {new Date(e.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [merchants, setMerchants] = useState([]);
  const [selected, setSelected] = useState(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    axios.get(`${API}/merchants/`).then(res => {
      setMerchants(res.data);
      if (res.data.length > 0) setSelected(res.data[0]);
    });
  }, [refresh]);

  const handlePayoutSuccess = () => {
    setRefresh(r => r + 1);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Playto Payout Engine</h1>
        <div className="grid grid-cols-3 gap-4 mb-6">
          {merchants.map(m => (
            <MerchantCard
              key={m.id}
              merchant={m}
              selected={selected?.id === m.id}
              onClick={() => setSelected(m)}
            />
          ))}
        </div>
        {selected && (
          <div className="flex flex-col gap-4">
            <PayoutForm merchant={selected} onSuccess={handlePayoutSuccess} />
            <PayoutsTable merchantId={selected.id} refresh={refresh} />
            <LedgerTable merchantId={selected.id} />
          </div>
        )}
      </div>
    </div>
  );
}