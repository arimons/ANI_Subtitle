import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import { Upload, FileVideo, CheckCircle, Loader2, AlertCircle, Download, Settings, Play } from 'lucide-react';
import { cn } from '../lib/utils';

interface Task {
    id: string;
    filename: string;
    status: string;
    progress: number;
    result?: string;
    streams?: any[]; // To store detected streams
    needsSelection?: boolean; // To trigger selection UI
}

export default function Dashboard() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [isDragging, setIsDragging] = useState(false);

    // Polling effect
    useEffect(() => {
        const interval = setInterval(async () => {
            // Filter tasks that need updates
            const activeTasks = tasks.filter(t =>
                t.status !== 'Completed' && !t.status.startsWith('Error')
            );

            if (activeTasks.length === 0) return;

            for (const task of activeTasks) {
                try {
                    const res = await axios.get(`http://127.0.0.1:8000/tasks/${task.id}`);
                    const { status, progress, result, streams, needs_selection } = res.data;

                    setTasks(prev => prev.map(t =>
                        t.id === task.id ? {
                            ...t,
                            status,
                            progress,
                            result,
                            streams,
                            needsSelection: needs_selection
                        } : t
                    ));
                } catch (e) {
                    console.error("Polling error", e);
                }
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [tasks]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback(async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        const files = Array.from(e.dataTransfer.files);
        if (files.length === 0) return;

        for (const file of files) {
            await uploadFile(file);
        }
    }, []);

    const uploadFile = async (file: File) => {
        const tempId = Math.random().toString(36).substring(7);
        const newTask: Task = {
            id: tempId,
            filename: file.name,
            status: 'Uploading...',
            progress: 0,
        };

        setTasks((prev) => [newTask, ...prev]);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post('http://127.0.0.1:8000/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (progressEvent) => {
                    const percentCompleted = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
                    setTasks((prev) =>
                        prev.map((t) => (t.id === tempId ? { ...t, progress: percentCompleted, status: `Uploading ${percentCompleted}%` } : t))
                    );
                },
            });

            const { task_id, status } = response.data;

            setTasks((prev) =>
                prev.map((t) => (t.id === tempId ? { ...t, id: task_id, status: status } : t))
            );

        } catch (error) {
            console.error('Upload failed:', error);
            setTasks((prev) =>
                prev.map((t) => (t.id === tempId ? { ...t, status: 'Error: Upload failed' } : t))
            );
        }
    };

    const startProcessing = async (taskId: string, mode: string, streamIndex?: number) => {
        try {
            await axios.post(`http://127.0.0.1:8000/tasks/${taskId}/start`, {
                mode,
                stream_index: streamIndex
            });
            // Force update status locally to avoid UI lag
            setTasks(prev => prev.map(t =>
                t.id === taskId ? { ...t, status: 'Queued', needsSelection: false } : t
            ));
        } catch (error) {
            console.error("Failed to start task", error);
        }
    };

    return (
        <div className="min-h-screen bg-background text-foreground p-8 font-sans">
            <div className="max-w-4xl mx-auto space-y-8">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">ANI 번역기</h1>
                        <p className="text-muted-foreground mt-1">AI 기반 애니메이션 자막 생성기</p>
                    </div>
                    <div className="flex gap-2">
                        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/10 text-green-500 text-xs font-medium border border-green-500/20">
                            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                            OpenAI 활성
                        </div>
                    </div>
                </div>

                {/* Drop Zone */}
                <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={cn(
                        "relative group cursor-pointer flex flex-col items-center justify-center w-full h-64 rounded-2xl border-2 border-dashed transition-all duration-300 ease-in-out",
                        isDragging
                            ? "border-primary bg-primary/5 scale-[1.01]"
                            : "border-border hover:border-primary/50 hover:bg-muted/50"
                    )}
                >
                    <div className="flex flex-col items-center gap-4 text-center">
                        <div className="p-4 rounded-full bg-muted group-hover:bg-background transition-colors">
                            <Upload className="w-8 h-8 text-muted-foreground group-hover:text-primary transition-colors" />
                        </div>
                        <div>
                            <p className="text-lg font-medium">동영상 파일을 이곳에 드래그하세요</p>
                            <p className="text-sm text-muted-foreground mt-1">MKV, MP4 지원</p>
                        </div>
                    </div>
                    <input
                        type="file"
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        onChange={(e) => {
                            if (e.target.files && e.target.files[0]) {
                                uploadFile(e.target.files[0]);
                            }
                        }}
                    />
                </div>

                {/* Task Columns */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                    {/* Active Tasks Column */}
                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold flex items-center gap-2">
                            <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                            진행 중인 작업
                        </h2>

                        {tasks.filter(t => t.status !== 'Completed' && !t.status.startsWith('Error')).length === 0 && (
                            <div className="text-center py-12 text-muted-foreground border rounded-xl border-dashed bg-muted/10">
                                진행 중인 작업이 없습니다
                            </div>
                        )}

                        <div className="grid gap-3">
                            {tasks.filter(t => t.status !== 'Completed' && !t.status.startsWith('Error')).map((task) => (
                                <div
                                    key={task.id}
                                    className="flex flex-col p-4 rounded-xl border bg-card hover:shadow-md transition-all gap-3"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="p-2 rounded-lg bg-muted/50">
                                            <FileVideo className="w-6 h-6 text-blue-500" />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between mb-1">
                                                <h3 className="font-medium truncate">{task.filename}</h3>
                                                <span className="text-xs font-medium px-2 py-0.5 rounded-full capitalize bg-blue-500/10 text-blue-500">
                                                    {task.status}
                                                </span>
                                            </div>

                                            {/* Progress Bar */}
                                            {!task.needsSelection && (
                                                <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-blue-500 transition-all duration-500"
                                                        style={{ width: `${task.progress}%` }}
                                                    />
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Selection UI */}
                                    {task.needsSelection && task.streams && (
                                        <div className="mt-2 p-4 bg-muted/30 rounded-lg border border-dashed border-yellow-500/30">
                                            <h4 className="text-sm font-semibold mb-3">작업 선택</h4>
                                            <div className="space-y-2">
                                                {task.streams.filter(s => s.codec_type === 'subtitle').map((stream, idx) => (
                                                    <button
                                                        key={idx}
                                                        onClick={() => startProcessing(task.id, 'extract', stream.index)}
                                                        className="w-full flex items-center justify-between p-2 text-sm bg-background hover:bg-accent rounded border transition-colors text-left"
                                                    >
                                                        <span>자막 추출 ({stream.tags?.language || 'Unknown'})</span>
                                                        <span className="text-xs text-muted-foreground">{stream.codec_name}</span>
                                                    </button>
                                                ))}

                                                <button
                                                    onClick={() => startProcessing(task.id, 'transcribe')}
                                                    className="w-full flex items-center justify-between p-2 text-sm bg-blue-500/10 hover:bg-blue-500/20 text-blue-500 rounded border border-blue-500/20 transition-colors text-left"
                                                >
                                                    <span className="flex items-center gap-2">
                                                        <Play className="w-3 h-3" />
                                                        오디오 자막 생성 (Whisper AI)
                                                    </span>
                                                    <span className="text-xs opacity-70">~20분 소요</span>
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Completed Tasks Column */}
                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold flex items-center gap-2">
                            <CheckCircle className="w-5 h-5 text-green-500" />
                            완료된 작업
                        </h2>

                        {tasks.filter(t => t.status === 'Completed' || t.status.startsWith('Error')).length === 0 && (
                            <div className="text-center py-12 text-muted-foreground border rounded-xl border-dashed bg-muted/10">
                                완료된 작업이 없습니다
                            </div>
                        )}

                        <div className="grid gap-3">
                            {tasks.filter(t => t.status === 'Completed' || t.status.startsWith('Error')).map((task) => (
                                <div
                                    key={task.id}
                                    className="flex flex-col p-4 rounded-xl border bg-card/50 hover:shadow-md transition-all gap-3"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="p-2 rounded-lg bg-muted/50">
                                            <FileVideo className="w-6 h-6 text-gray-500" />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between mb-1">
                                                <h3 className="font-medium truncate text-muted-foreground">{task.filename}</h3>
                                                <span className={cn(
                                                    "text-xs font-medium px-2 py-0.5 rounded-full capitalize",
                                                    task.status === 'Completed' ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                                                )}>
                                                    {task.status === 'Completed' ? '완료됨' : '오류'}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Result Section */}
                                    {task.status === 'Completed' && task.result && (
                                        <div className="flex items-center justify-between p-3 bg-green-500/5 rounded-lg text-sm border border-green-500/20">
                                            <span className="text-muted-foreground truncate flex-1 mr-4 text-xs">
                                                {task.result.split(/[/\\]/).pop()}
                                            </span>
                                            <button
                                                className="flex items-center gap-1 text-green-600 hover:text-green-700 font-bold text-xs px-3 py-1.5 bg-green-100 rounded-md transition-colors"
                                                onClick={() => {
                                                    if (task.result) {
                                                        const filename = task.result.split(/[/\\]/).pop();
                                                        window.open(`http://127.0.0.1:8000/download/${filename}`, '_blank');
                                                    }
                                                }}
                                            >
                                                <Download className="w-3 h-3" />
                                                다운로드
                                            </button>
                                        </div>
                                    )}

                                    {task.status.startsWith('Error') && (
                                        <div className="p-3 bg-red-500/5 rounded-lg text-sm text-red-500 border border-red-500/20">
                                            {task.status}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}
