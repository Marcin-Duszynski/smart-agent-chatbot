/**
 * File Management System for Python MCP Server
 * Handles session-based file storage and download functionality
 */

import { join, basename, extname } from '@std/path'
import { ensureDir, exists } from '@std/fs'
// Note: Using JSZip for better compatibility
// import { compress } from "https://deno.land/x/zip@v1.2.3/mod.ts"

export interface FileInfo {
  name: string
  path: string
  size: number
  sizeHuman: string
  type: string
  extension: string
  created: number
  description: string
  containedFiles?: { name: string; size: string }[]
  // Base64 data for direct download
  base64Data?: string
}

export interface SessionFiles {
  sessionId: string
  executionNumber: number
  files: FileInfo[]
  zipFile?: FileInfo
}

export class FileManager {
  private baseDir = '/tmp/mcp-python-sessions'
  
  constructor() {
    this.ensureBaseDir()
  }
  
  private async ensureBaseDir() {
    await ensureDir(this.baseDir)
  }
  
  /**
   * Get session directory path
   */
  getSessionDir(sessionId: string): string {
    return join(this.baseDir, sessionId)
  }
  
  /**
   * Get execution directory path
   */
  getExecutionDir(sessionId: string, executionNumber: number): string {
    return join(this.getSessionDir(sessionId), `execution_${executionNumber.toString().padStart(3, '0')}`)
  }
  
  /**
   * Ensure session directory exists
   */
  async ensureSessionDir(sessionId: string): Promise<string> {
    const sessionDir = this.getSessionDir(sessionId)
    await ensureDir(sessionDir)
    return sessionDir
  }
  
  /**
   * Ensure execution directory exists  
   */
  async ensureExecutionDir(sessionId: string, executionNumber: number): Promise<string> {
    const execDir = this.getExecutionDir(sessionId, executionNumber)
    await ensureDir(execDir)
    return execDir
  }
  
  /**
   * Save executed Python code as file
   */
  async saveCodeFile(sessionId: string, executionNumber: number, code: string, result: any): Promise<string> {
    const execDir = await this.ensureExecutionDir(sessionId, executionNumber)
    const filename = `script_${executionNumber.toString().padStart(3, '0')}.py`
    const filepath = join(execDir, filename)
    
    const header = [
      `# Python Code Execution - ${new Date().toISOString()}`,
      `# Session ID: ${sessionId}`,
      `# Execution #${executionNumber}`,
      `# Status: ${result.status}`,
      `# Execution Time: ${result.executionTime || 'N/A'}ms`,
      '',
      code
    ].join('\n')
    
    await Deno.writeTextFile(filepath, header)
    return filepath
  }
  
  /**
   * Save execution output as text file  
   */
  async saveOutputFile(sessionId: string, executionNumber: number, output: string[]): Promise<string> {
    const execDir = await this.ensureExecutionDir(sessionId, executionNumber)
    const filename = `output_${executionNumber.toString().padStart(3, '0')}.txt`
    const filepath = join(execDir, filename)
    
    const content = [
      `Python Code Execution Output - ${new Date().toISOString()}`,
      `Session ID: ${sessionId}`,
      `Execution #${executionNumber}`,
      '='.repeat(50),
      '',
      ...output
    ].join('\n')
    
    await Deno.writeTextFile(filepath, content)
    return filepath
  }
  
  /**
   * Save return value as JSON file if it's structured data
   */
  async saveReturnValueFile(sessionId: string, executionNumber: number, returnValue: string | null): Promise<string | null> {
    if (!returnValue) return null
    
    const execDir = await this.ensureExecutionDir(sessionId, executionNumber)
    const filename = `return_value_${executionNumber.toString().padStart(3, '0')}.json`
    const filepath = join(execDir, filename)
    
    try {
      // Try to parse and pretty-print JSON
      const parsed = JSON.parse(returnValue)
      const prettyJson = JSON.stringify(parsed, null, 2)
      await Deno.writeTextFile(filepath, prettyJson)
      return filepath
    } catch {
      // If not valid JSON, save as text
      const textFilename = `return_value_${executionNumber.toString().padStart(3, '0')}.txt`
      const textFilepath = join(execDir, textFilename)
      await Deno.writeTextFile(textFilepath, returnValue)
      return textFilepath
    }
  }
  
  /**
   * Analyze file and extract metadata
   */
  async analyzeFile(filepath: string, sessionId: string): Promise<FileInfo> {
    const stat = await Deno.stat(filepath)
    const name = basename(filepath)
    const ext = extname(filepath).toLowerCase()
    
    return {
      name,
      path: filepath,
      size: stat.size,
      sizeHuman: this.formatFileSize(stat.size),
      type: this.getFileType(ext),
      extension: ext,
      created: stat.mtime?.getTime() || Date.now(),
      description: this.getFileDescription(name, ext),
    }
  }
  
  /**
   * Get all files from an execution directory
   */
  async getExecutionFiles(sessionId: string, executionNumber: number): Promise<FileInfo[]> {
    const execDir = this.getExecutionDir(sessionId, executionNumber)
    
    if (!await exists(execDir)) {
      return []
    }
    
    const files: FileInfo[] = []
    
    try {
      for await (const entry of Deno.readDir(execDir)) {
        if (entry.isFile) {
          const filepath = join(execDir, entry.name)
          const fileInfo = await this.analyzeFile(filepath, sessionId)
          files.push(fileInfo)
        }
      }
    } catch (error) {
      console.error(`Error reading execution directory ${execDir}:`, error)
    }
    
    return files.sort((a, b) => a.name.localeCompare(b.name))
  }
  
  /**
   * Create ZIP file with all execution files
   */
  async createZipFile(sessionId: string, executionNumber: number): Promise<FileInfo | null> {
    // Note: This would require a ZIP library in Deno
    // For now, return null - can be implemented with a ZIP library
    return null
  }
  
  /**
   * Get file type based on extension
   */
  private getFileType(ext: string): string {
    const imageExts = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp']
    const dataExts = ['.csv', '.json', '.xlsx', '.xls', '.parquet', '.tsv']
    const documentExts = ['.pdf', '.html', '.md', '.txt', '.docx', '.doc']
    const codeExts = ['.py', '.js', '.ts', '.sql', '.r', '.ipynb']
    
    if (imageExts.includes(ext)) return 'image'
    if (dataExts.includes(ext)) return 'data'  
    if (documentExts.includes(ext)) return 'document'
    if (codeExts.includes(ext)) return 'code'
    return 'file'
  }
  
  /**
   * Get file description based on name and extension
   */
  private getFileDescription(name: string, ext: string): string {
    if (name.startsWith('script_')) return 'Executed Python script'
    if (name.startsWith('output_')) return 'Execution output'
    if (name.startsWith('return_value_')) return 'Execution return value'
    
    const type = this.getFileType(ext)
    switch (type) {
      case 'image': return 'Generated image file'
      case 'data': return 'Data file'
      case 'document': return 'Document file'
      case 'code': return 'Code file'
      default: return 'Generated file'
    }
  }
  
  /**
   * Format file size in human readable format
   */
  private formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B'
    
    const units = ['B', 'KB', 'MB', 'GB']
    let size = bytes
    let unitIndex = 0
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`
  }
  
  /**
   * Detect additional files generated during Python execution
   */
  async detectGeneratedFiles(sessionId: string, executionNumber: number): Promise<string[]> {
    const execDir = this.getExecutionDir(sessionId, executionNumber)
    const detectedFiles: string[] = []
    
    try {
      // Get current working directory (where Python code ran)
      const currentDir = Deno.cwd()
      
      // List files in current directory and look for newly created files
      for await (const entry of Deno.readDir(currentDir)) {
        if (entry.isFile) {
          const filename = entry.name
          const sourceFile = join(currentDir, filename)
          
          // Skip if it's a Python file (likely the executed script itself)
          if (filename.endsWith('.py')) continue
          
          // Skip common system/temp files
          if (filename.startsWith('.') || filename.includes('__pycache__')) continue
          
          try {
            // Move file to execution directory
            const destFile = join(execDir, filename)
            await Deno.copyFile(sourceFile, destFile)
            await Deno.remove(sourceFile) // Clean up original
            detectedFiles.push(destFile)
            console.log(`Detected and moved generated file: ${filename}`)
          } catch (error) {
            console.warn(`Failed to move file ${filename}:`, error)
          }
        }
      }
    } catch (error) {
      console.warn(`Error detecting generated files for session ${sessionId}:`, error)
    }
    
    return detectedFiles
  }
  
  /**
   * Create ZIP file as Base64 data for direct download
   */
  async createBase64ZipFile(
    files: FileInfo[], 
    sessionId: string, 
    executionNumber: number
  ): Promise<FileInfo | null> {
    if (files.length === 0) return null;
    
    try {
      const zipFileName = `python_execution_${executionNumber.toString().padStart(3, '0')}.zip`;
      
      // Create ZIP file with all files using JSZip
      const JSZip = (await import("npm:jszip@3.10.1")).default;
      const zip = new JSZip();
      
      for (const file of files) {
        const content = await Deno.readFile(file.path);
        zip.file(file.name, content);
      }
      
      const zipData = await zip.generateAsync({ type: "uint8array" });
      
      // Convert to Base64
      const base64Data = btoa(String.fromCharCode(...zipData));
      
      console.log(`📦 Created Base64 ZIP file: ${zipFileName} (${zipData.length} bytes)`);
      
      return {
        name: zipFileName,
        path: '', // No local path for Base64 data
        size: zipData.length,
        sizeHuman: this.formatFileSize(zipData.length),
        type: 'archive',
        extension: '.zip',
        created: Date.now(),
        description: `Archive containing ${files.length} generated files`,
        containedFiles: files.map(f => ({ name: f.name, size: f.sizeHuman })),
        // Store Base64 data for download
        base64Data: base64Data
      };
      
    } catch (error) {
      console.error('Failed to create Base64 ZIP file:', error);
      return null;
    }
  }

  /**
   * Clean up old sessions (keep only last N executions)
   */
  async cleanupSession(sessionId: string, keepLast = 10) {
    const sessionDir = this.getSessionDir(sessionId)
    
    if (!await exists(sessionDir)) return
    
    const execDirs: { name: string; created: number }[] = []
    
    try {
      for await (const entry of Deno.readDir(sessionDir)) {
        if (entry.isDirectory && entry.name.startsWith('execution_')) {
          const stat = await Deno.stat(join(sessionDir, entry.name))
          execDirs.push({
            name: entry.name,
            created: stat.mtime?.getTime() || 0
          })
        }
      }
      
      // Sort by creation time (newest first)
      execDirs.sort((a, b) => b.created - a.created)
      
      // Remove old directories
      const toRemove = execDirs.slice(keepLast)
      for (const dir of toRemove) {
        const dirPath = join(sessionDir, dir.name)
        await Deno.remove(dirPath, { recursive: true })
        console.log(`Cleaned up old execution directory: ${dirPath}`)
      }
      
    } catch (error) {
      console.error(`Error cleaning up session ${sessionId}:`, error)
    }
  }
}