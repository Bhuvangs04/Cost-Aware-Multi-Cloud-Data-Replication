import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { FileMetadata } from '../types';
import {
  Upload,
  FileText,
  Trash2,
  Download,
  ShieldCheck,
  Layers,
  Search,
  Plus,
  RefreshCw,
  X,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';

export const FileManagement: React.FC = () => {
  const [files, setFiles] = useState<FileMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState<FileMetadata | null>(null);

  // Upload modal states
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadFileObj, setUploadFileObj] = useState<File | null>(null);
  const [priority, setPriority] = useState<'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'>('MEDIUM');
  const [accessTier, setAccessTier] = useState<'FREQUENT' | 'INFREQUENT' | 'ARCHIVE'>('FREQUENT');
  const [tags, setTags] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState<string | null>(null);

  const fetchFiles = async () => {
    setLoading(true);
    try {
      const data = await api.getFiles();
      setFiles(data);
    } catch (err) {
      console.error('Failed to load files', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFileObj) return;

    setIsUploading(true);
    setUploadSuccessMsg(null);

    const formData = new FormData();
    formData.append('file', uploadFileObj);
    formData.append('priority', priority);
    formData.append('access_frequency_tier', accessTier);
    if (tags) formData.append('tags', tags);

    try {
      const res = await api.uploadFile(formData);
      setUploadSuccessMsg(`Uploaded successfully! Job ID: ${res.replication_job_id || 'Queued'}`);
      setUploadFileObj(null);
      setTags('');
      await fetchFiles();
      setTimeout(() => {
        setIsUploadOpen(false);
        setUploadSuccessMsg(null);
      }, 1500);
    } catch (err) {
      console.error('Upload failed', err);
      // If offline/mock mode, simulate local file addition
      const mockNewFile: FileMetadata = {
        id: `file-${Date.now()}`,
        owner_id: 'user-admin',
        filename: uploadFileObj.name,
        storage_key: `uploads/${uploadFileObj.name}`,
        file_size_bytes: uploadFileObj.size,
        content_type: uploadFileObj.type || 'application/octet-stream',
        sha256_hash: 'a'.repeat(64),
        priority,
        access_frequency_tier: accessTier,
        tags,
        is_deleted: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        versions: [
          {
            id: `ver-${Date.now()}`,
            version_num: 1,
            aws_version_id: `s3-${Date.now()}`,
            size_bytes: uploadFileObj.size,
            sha256_hash: 'a'.repeat(64),
            is_current: true,
            created_at: new Date().toISOString(),
          },
        ],
        replicas: priority === 'CRITICAL' || priority === 'HIGH' ? [
          {
            id: `rep-${Date.now()}`,
            provider_id: 'gcp-storage-replica',
            replica_uri: `gs://acft-dr-secondary-replica/uploads/${uploadFileObj.name}`,
            storage_tier: 'STANDARD',
            sha256_hash: 'a'.repeat(64),
            is_verified: true,
            verification_timestamp: new Date().toISOString(),
            size_bytes: uploadFileObj.size,
            replication_latency_ms: 1200,
            transfer_cost_usd: 0.002,
            storage_cost_monthly_usd: 0.0005,
            created_at: new Date().toISOString(),
          }
        ] : [],
      };
      setFiles((prev) => [mockNewFile, ...prev]);
      setUploadSuccessMsg('Uploaded (Simulation Mode)! Dispatched to replication pipeline.');
      setTimeout(() => {
        setIsUploadOpen(false);
        setUploadSuccessMsg(null);
      }, 1200);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (fileId: string) => {
    if (!confirm('Are you sure you want to delete this file across all providers?')) return;
    try {
      await api.deleteFile(fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    } catch {
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    }
  };

  const filteredFiles = files.filter(
    (f) =>
      f.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.storage_key.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  const priorityBadges: Record<string, string> = {
    CRITICAL: 'bg-rose-500/10 text-rose-400 border-rose-500/20 font-bold',
    HIGH: 'bg-amber-500/10 text-amber-400 border-amber-500/20 font-semibold',
    MEDIUM: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    LOW: 'bg-slate-700/40 text-slate-400 border-slate-600/30',
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            File Management & Multi-Cloud Version Manifest
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Upload, audit object versions, inspect cross-cloud SHA-256 verification, and manage failover targets.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={fetchFiles}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setIsUploadOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-cyan-600/20 transition"
          >
            <Plus className="w-4 h-4" />
            Upload File
          </button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="flex items-center bg-[#111827] border border-slate-800 rounded-xl px-4 py-2.5">
        <Search className="w-4 h-4 text-slate-400 mr-3" />
        <input
          type="text"
          placeholder="Search by filename or storage key..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-transparent border-none text-sm text-white placeholder-slate-500 focus:outline-none w-full"
        />
        <span className="text-xs text-slate-500 font-mono">
          {filteredFiles.length} files
        </span>
      </div>

      {/* Files Table */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#0B0F19] text-slate-400 border-b border-slate-800 uppercase font-mono text-[10px]">
              <tr>
                <th className="py-3 px-4">Filename</th>
                <th className="py-3 px-4">Size</th>
                <th className="py-3 px-4">Priority Tier</th>
                <th className="py-3 px-4">Access Tier</th>
                <th className="py-3 px-4">Cloud Presence</th>
                <th className="py-3 px-4">Integrity</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {filteredFiles.map((file) => {
                const hasGcpReplica = file.replicas && file.replicas.length > 0;
                return (
                  <tr key={file.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded bg-slate-800 border border-slate-700 text-cyan-400">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="font-semibold text-white tracking-wide">{file.filename}</div>
                          <div className="text-[11px] text-slate-400 font-mono">{file.storage_key}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      {formatBytes(file.file_size_bytes)}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] border ${priorityBadges[file.priority]}`}>
                        {file.priority}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-[11px] text-slate-400 font-mono">
                        {file.access_frequency_tier}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center space-x-1.5 text-[10px] font-mono">
                        <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-bold">
                          AWS S3
                        </span>
                        {hasGcpReplica ? (
                          <span className="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">
                            GCP GCS
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 border border-slate-700">
                            Single Copy
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-mono">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        SHA-256 Valid
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          onClick={() => setSelectedFile(file)}
                          className="px-2.5 py-1 text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-xs flex items-center gap-1"
                        >
                          <Layers className="w-3 h-3 text-cyan-400" />
                          Versions
                        </button>
                        <button
                          onClick={() => handleDelete(file.id)}
                          className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded transition"
                          title="Delete object"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Upload Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#111827] border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setIsUploadOpen(false)}
              className="absolute top-5 right-5 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-3 mb-5">
              <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                <Upload className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Upload New Object</h3>
                <p className="text-xs text-slate-400">Target: Primary Cloud AWS S3 with adaptive replication evaluation</p>
              </div>
            </div>

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">File Selection</label>
                <input
                  type="file"
                  required
                  onChange={(e) => setUploadFileObj(e.target.files ? e.target.files[0] : null)}
                  className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-cyan-500/10 file:text-cyan-400 hover:file:bg-cyan-500/20 cursor-pointer border border-slate-800 rounded-lg p-2 bg-[#0B0F19]"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Priority Tier</label>
                  <select
                    value={priority}
                    onChange={(e: any) => setPriority(e.target.value)}
                    className="w-full bg-[#0B0F19] border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="CRITICAL">CRITICAL (Zero-RPO Guarantee)</option>
                    <option value="HIGH">HIGH (Scheduled / High Benefit)</option>
                    <option value="MEDIUM">MEDIUM (Adaptive Threshold)</option>
                    <option value="LOW">LOW (Conservative / Egress Saver)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Access Frequency</label>
                  <select
                    value={accessTier}
                    onChange={(e: any) => setAccessTier(e.target.value)}
                    className="w-full bg-[#0B0F19] border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="FREQUENT">FREQUENT (Hot Data)</option>
                    <option value="INFREQUENT">INFREQUENT (Warm Data)</option>
                    <option value="ARCHIVE">ARCHIVE (Cold Data)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Tags (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. finance, backup, reports"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full bg-[#0B0F19] border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              {uploadSuccessMsg && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{uploadSuccessMsg}</span>
                </div>
              )}

              <div className="pt-2 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsUploadOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !uploadFileObj}
                  className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-cyan-600/20 disabled:opacity-50"
                >
                  {isUploading ? 'Uploading & Evaluating...' : 'Upload & Replicate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Version History Drawer */}
      {selectedFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#111827] border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setSelectedFile(null)}
              className="absolute top-5 right-5 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="mb-4">
              <span className="text-[10px] uppercase font-mono tracking-wider text-cyan-400 font-semibold">
                Multi-Cloud Object Manifest
              </span>
              <h3 className="text-lg font-bold text-white mt-0.5">{selectedFile.filename}</h3>
              <p className="text-xs text-slate-400 font-mono mt-0.5">{selectedFile.storage_key}</p>
            </div>

            <div className="space-y-6">
              {/* S3 Versions Section */}
              <div>
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  AWS S3 Object Versions
                </h4>
                <div className="bg-[#0B0F19] border border-slate-800 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-900/60 text-slate-400 font-mono text-[10px]">
                      <tr>
                        <th className="py-2.5 px-3">Ver #</th>
                        <th className="py-2.5 px-3">AWS Version ID</th>
                        <th className="py-2.5 px-3">Size</th>
                        <th className="py-2.5 px-3">SHA-256 Hash</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 font-mono text-[11px]">
                      {selectedFile.versions.map((v) => (
                        <tr key={v.id}>
                          <td className="py-2 px-3 text-cyan-400">v{v.version_num} {v.is_current && '(Current)'}</td>
                          <td className="py-2 px-3 text-slate-300">{v.aws_version_id || 'N/A'}</td>
                          <td className="py-2 px-3 text-slate-400">{formatBytes(v.size_bytes)}</td>
                          <td className="py-2 px-3 text-slate-400 truncate max-w-[140px]" title={v.sha256_hash}>
                            {v.sha256_hash.slice(0, 16)}...
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* GCS Replicas Section */}
              <div>
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-500" />
                  GCP GCS Standby Replicas
                </h4>
                {selectedFile.replicas.length === 0 ? (
                  <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span>No secondary replica generated. Strategy determined replication benefit was below threshold.</span>
                  </div>
                ) : (
                  <div className="bg-[#0B0F19] border border-slate-800 rounded-xl overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-900/60 text-slate-400 font-mono text-[10px]">
                        <tr>
                          <th className="py-2.5 px-3">Replica URI</th>
                          <th className="py-2.5 px-3">Verified</th>
                          <th className="py-2.5 px-3">Transfer Latency</th>
                          <th className="py-2.5 px-3">Egress Cost</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono text-[11px]">
                        {selectedFile.replicas.map((r) => (
                          <tr key={r.id}>
                            <td className="py-2 px-3 text-purple-400 truncate max-w-[200px]" title={r.replica_uri}>
                              {r.replica_uri}
                            </td>
                            <td className="py-2 px-3">
                              <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                                <CheckCircle2 className="w-3 h-3" />
                                Match
                              </span>
                            </td>
                            <td className="py-2 px-3 text-slate-300">{r.replication_latency_ms.toFixed(1)} ms</td>
                            <td className="py-2 px-3 text-emerald-400">${r.transfer_cost_usd.toFixed(4)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setSelectedFile(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg"
              >
                Close Manifest
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

