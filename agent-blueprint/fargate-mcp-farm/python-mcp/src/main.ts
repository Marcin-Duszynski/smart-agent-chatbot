/// <reference types="npm:@types/node@22.12.0" />

import './polyfill.ts'
import http from 'node:http'
import { randomUUID } from 'node:crypto'
import { parseArgs } from '@std/cli/parse-args'
import { join } from '@std/path'
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js'
import { isInitializeRequest } from '@modelcontextprotocol/sdk/types.js'
import { type LoggingLevel, SetLevelRequestSchema, ListResourcesRequestSchema, ReadResourceRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { z } from 'zod'

import { asXml, runCode } from './runCode.ts'
import { FileManager, type FileInfo } from './fileManager.ts'
import { Buffer } from 'node:buffer'

/*
 * XML escaping utility
 */
function escapeClosing(closingTag: string): (str: string) => string {
  const regex = new RegExp(`</?\\s*${closingTag}(?:.*?>)?`, 'gi')
  const onMatch = (match: string) => {
    return match.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
  return (str: string) => str.replace(regex, onMatch)
}

/*
 * Enhanced asXml function that includes file information
 */
function asXmlWithFiles(
  runResult: any, 
  files: FileInfo[], 
  zipFile: FileInfo | null, 
  sessionId: string
): string {
  // Start with base XML structure
  const xml = [`<status>${runResult.status}</status>`]
  
  if (runResult.dependencies?.length) {
    xml.push(`<dependencies>${JSON.stringify(runResult.dependencies)}</dependencies>`)
  }
  
  if (runResult.output.length) {
    xml.push('<output>')
    const escapeXml = escapeClosing('output')
    xml.push(...runResult.output.map(escapeXml))
    xml.push('</output>')
  }
  
  if (runResult.status == 'success') {
    if (runResult.returnValueJson) {
      xml.push('<return_value>')
      xml.push(escapeClosing('return_value')(runResult.returnValueJson))
      xml.push('</return_value>')
    }
  } else {
    xml.push('<error>')
    xml.push(escapeClosing('error')(runResult.error || 'Unknown error'))
    xml.push('</error>')
  }
  
  // Add files section with proper XML escaping
  if (zipFile && zipFile.base64Data) {
    xml.push('<files>')
    xml.push(`<archive name="${escapeClosing('archive')(zipFile.name)}" size="${zipFile.sizeHuman}">`)
    xml.push(`<contains>${zipFile.containedFiles?.map(f => `${escapeClosing('contains')(f.name)} (${f.size})`).join(', ')}</contains>`)
    xml.push(`<download>data:application/zip;base64,${zipFile.base64Data}</download>`)
    xml.push('</archive>')
    xml.push('</files>')
  } else if (files.length > 0) {
    xml.push('<files>')
    for (const file of files) {
      xml.push(`<file name="${escapeClosing('file')(file.name)}" size="${file.sizeHuman}" type="${file.type}">`)
      xml.push(`<description>${escapeClosing('description')(file.description)}</description>`)
      xml.push(`<resource>mcp-python://session/${sessionId}/file/${file.name}</resource>`)
      xml.push('</file>')
    }
    xml.push('</files>')
  }
  
  return `<result>\n${xml.map(line => `  ${line}`).join('\n')}\n</result>`
}

const VERSION = '0.0.13'

export async function main() {
  const { args } = Deno
  if (args.length === 1 && args[0] === 'stdio') {
    await runStdio()
  } else if (args.length >= 1 && args[0] === 'streamable_http') {
    const flags = parseArgs(Deno.args, {
      string: ['port'],
      default: { port: '3001' },
    })
    const port = parseInt(flags.port)
    runStreamableHttp(port)
  } else if (args.length >= 1 && args[0] === 'sse') {
    const flags = parseArgs(Deno.args, {
      string: ['port'],
      default: { port: '3001' },
    })
    const port = parseInt(flags.port)
    runSse(port)
  } else if (args.length === 1 && args[0] === 'warmup') {
    await warmup()
  } else {
    console.error(
      `\
Invalid arguments.

Usage: deno run -N -R=node_modules -W=node_modules --node-modules-dir=auto jsr:@pydantic/mcp-run-python [stdio|streamable_http|sse|warmup]

options:
  --port <port>  Port to run the SSE server on (default: 3001)`,
    )
    Deno.exit(1)
  }
}


/*
 * Get content type based on file extension
 */
function getContentType(filename: string): string {
  const ext = filename.toLowerCase().split('.').pop()
  const mimeTypes: { [key: string]: string } = {
    'py': 'text/x-python',
    'txt': 'text/plain',
    'json': 'application/json',
    'csv': 'text/csv',
    'html': 'text/html',
    'pdf': 'application/pdf',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'svg': 'image/svg+xml',
    'zip': 'application/zip'
  }
  return mimeTypes[ext || ''] || 'application/octet-stream'
}

/*
 * Create an MCP server with the `run_python_code` tool registered.
 */
function createServer(): McpServer {
  const server = new McpServer(
    {
      name: 'MCP Run Python',
      version: VERSION,
    },
    {
      instructions: 'Call the "run_python_code" tool with the Python code to run.',
      capabilities: {
        logging: {},
        resources: {
          subscribe: false,
          listChanged: false
        },
      },
    },
  )

  const toolDescription = `Tool to execute Python code and return stdout, stderr, and return value.

The code may be async, and the value on the last line will be returned as the return value.

The code will be executed with Python 3.12.

Dependencies may be defined via PEP 723 script metadata, e.g. to install "pydantic", the script should start
with a comment of the form:

# /// script
# dependencies = ['pydantic']
# ///
print('python code here')
`

  let setLogLevel: LoggingLevel = 'emergency'

  server.server.setRequestHandler(SetLevelRequestSchema, (request) => {
    setLogLevel = request.params.level
    return {}
  })

  // Resources handlers
  server.server.setRequestHandler(ListResourcesRequestSchema, async () => {
    const resources = []
    
    // List all available file resources from all sessions
    const baseDir = '/tmp/mcp-python-sessions'
    try {
      for await (const sessionEntry of Deno.readDir(baseDir)) {
        if (sessionEntry.isDirectory) {
          const sessionId = sessionEntry.name
          const sessionDir = `${baseDir}/${sessionId}`
          
          for await (const execEntry of Deno.readDir(sessionDir)) {
            if (execEntry.isDirectory && execEntry.name.startsWith('execution_')) {
              const execDir = `${sessionDir}/${execEntry.name}`
              
              for await (const fileEntry of Deno.readDir(execDir)) {
                if (fileEntry.isFile) {
                  const filePath = `${execDir}/${fileEntry.name}`
                  const stat = await Deno.stat(filePath)
                  
                  resources.push({
                    uri: `mcp-python://session/${sessionId}/file/${fileEntry.name}`,
                    name: fileEntry.name,
                    description: `Generated file from Python execution in session ${sessionId}`,
                    mimeType: getContentType(fileEntry.name)
                  })
                }
              }
            }
          }
        }
      }
    } catch (error) {
      // Directory might not exist yet
    }
    
    return { resources }
  })

  server.server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const uri = request.params.uri
    
    // Parse URI: mcp-python://session/{sessionId}/file/{filename}
    const match = uri.match(/^mcp-python:\/\/session\/([^\/]+)\/file\/(.+)$/)
    if (!match) {
      throw new Error(`Invalid resource URI: ${uri}`)
    }
    
    const [, sessionId, filename] = match
    const baseDir = '/tmp/mcp-python-sessions'
    const sessionDir = `${baseDir}/${sessionId}`
    
    // Find the file in any execution directory
    let filePath: string | null = null
    try {
      for await (const execEntry of Deno.readDir(sessionDir)) {
        if (execEntry.isDirectory && execEntry.name.startsWith('execution_')) {
          const execDir = `${sessionDir}/${execEntry.name}`
          const candidatePath = `${execDir}/${filename}`
          
          try {
            const stat = await Deno.stat(candidatePath)
            if (stat.isFile) {
              filePath = candidatePath
              break
            }
          } catch {
            // File doesn't exist, continue searching
          }
        }
      }
    } catch {
      // Session directory doesn't exist
    }
    
    if (!filePath) {
      throw new Error(`Resource not found: ${uri}`)
    }
    
    // Determine if it's text or binary
    const mimeType = getContentType(filename)
    const isText = mimeType.startsWith('text/') || 
                   mimeType === 'application/json' ||
                   filename.endsWith('.py')
    
    if (isText) {
      const content = await Deno.readTextFile(filePath)
      return {
        contents: [{
          uri,
          mimeType,
          text: content
        }]
      }
    } else {
      const content = await Deno.readFile(filePath)
      const base64Content = btoa(String.fromCharCode(...content))
      return {
        contents: [{
          uri,
          mimeType,
          blob: base64Content
        }]
      }
    }
  })

  // Session-based execution counters
  const sessionExecutions: { [sessionId: string]: number } = {}
  const fileManager = new FileManager()

  server.tool(
    'run_python_code',
    toolDescription,
    { python_code: z.string().describe('Python code to run') },
    async ({ python_code }: { python_code: string }) => {
      const logPromises: Promise<void>[] = []
      
      // Generate unique session for this execution  
      // Note: In a production setup, this would be provided by the MCP transport
      const sessionId = crypto.randomUUID()
      
      // Track execution number for this session
      if (!sessionExecutions[sessionId]) {
        sessionExecutions[sessionId] = 0
      }
      sessionExecutions[sessionId]++
      const executionNumber = sessionExecutions[sessionId]
      
      const result = await runCode([{
        name: 'main.py',
        content: python_code,  
        active: true,
      }], (level, data) => {
        if (LogLevels.indexOf(level) >= LogLevels.indexOf(setLogLevel)) {
          logPromises.push(server.server.sendLoggingMessage({ level, data }))
        }
      })
      
      await Promise.all(logPromises)
      
      // Save files for successful or failed executions
      try {
        const files: FileInfo[] = []
        
        // Save executed code
        const codeFile = await fileManager.saveCodeFile(sessionId, executionNumber, python_code, result)
        files.push(await fileManager.analyzeFile(codeFile, sessionId))
        
        // Save output if any
        if (result.output && result.output.length > 0) {
          const outputFile = await fileManager.saveOutputFile(sessionId, executionNumber, result.output)
          files.push(await fileManager.analyzeFile(outputFile, sessionId))
        }
        
        // Save return value if any
        if (result.status === 'success' && result.returnValueJson) {
          const returnFile = await fileManager.saveReturnValueFile(sessionId, executionNumber, result.returnValueJson)
          if (returnFile) {
            files.push(await fileManager.analyzeFile(returnFile, sessionId))
          }
        }
        
        // Process files extracted from Pyodide virtual filesystem
        if (result.status === 'success' && result.generatedFiles) {
          const execDir = await fileManager.ensureExecutionDir(sessionId, executionNumber)
          
          for (const generatedFile of result.generatedFiles) {
            try {
              const filePath = join(execDir, generatedFile.name)
              await Deno.writeFile(filePath, generatedFile.content)
              files.push(await fileManager.analyzeFile(filePath, sessionId))
              console.log(`Saved Pyodide file: ${generatedFile.name} (${generatedFile.content.length} bytes)`)
            } catch (error) {
              console.warn(`Failed to save Pyodide file ${generatedFile.name}:`, error)
            }
          }
        }
        
        // Detect and collect any additional files created during execution (fallback)
        const additionalFiles = await fileManager.detectGeneratedFiles(sessionId, executionNumber)
        for (const additionalFile of additionalFiles) {
          files.push(await fileManager.analyzeFile(additionalFile, sessionId))
        }
        
        // Create Base64 ZIP file if files were generated
        let zipFile: FileInfo | null = null
        if (files.length > 0) {
          zipFile = await fileManager.createBase64ZipFile(files, sessionId, executionNumber)
        }
        
        // Generate response using asXml but with file information added
        let responseText = asXmlWithFiles(result, files, zipFile, sessionId)
        
        // Cleanup old executions to prevent disk bloat  
        await fileManager.cleanupSession(sessionId, 5)
        
        return {
          content: [{ type: 'text', text: responseText }],
        }
        
      } catch (fileError) {
        console.error('File management error:', fileError)
        // Return original result even if file management fails
        return {
          content: [{ type: 'text', text: asXml(result) }],
        }
      }
    },
  )
  return server
}

/*
 * Define some QOL functions for both the SSE and Streamable HTTP server implementation
 */
function httpGetUrl(req: http.IncomingMessage): URL {
  return new URL(
    req.url ?? '',
    `http://${req.headers.host ?? 'unknown'}`,
  )
}

function httpGetBody(req: http.IncomingMessage): Promise<JSON> {
  // https://nodejs.org/en/learn/modules/anatomy-of-an-http-transaction#request-body
  return new Promise((resolve) => {
    // deno-lint-ignore no-explicit-any
    const bodyParts: any[] = []
    let body
    req.on('data', (chunk) => {
      bodyParts.push(chunk)
    }).on('end', () => {
      body = Buffer.concat(bodyParts).toString()
      resolve(JSON.parse(body))
    })
  })
}

function httpSetTextResponse(res: http.ServerResponse, status: number, text: string) {
  res.setHeader('Content-Type', 'text/plain')
  res.statusCode = status
  res.end(`${text}\n`)
}

function httpSetJsonResponse(res: http.ServerResponse, status: number, text: string, code: number) {
  res.setHeader('Content-Type', 'application/json')
  res.statusCode = status
  res.write(JSON.stringify({
    jsonrpc: '2.0',
    error: {
      code: code,
      message: text,
    },
    id: null,
  }))
  res.end()
}

/*
 * Run the MCP server using the Streamable HTTP transport
 */
function runStreamableHttp(port: number) {
  // https://github.com/modelcontextprotocol/typescript-sdk?tab=readme-ov-file#with-session-management
  const mcpServer = createServer()
  const transports: { [sessionId: string]: StreamableHTTPServerTransport } = {}
  const fileManager = new FileManager()

  const server = http.createServer(async (req, res) => {
    const url = httpGetUrl(req)
    let pathMatch = false
    function match(method: string, path: string): boolean {
      if (url.pathname === path) {
        pathMatch = true
        return req.method === method
      }
      return false
    }

    // Reusable handler for GET and DELETE requests
    async function handleSessionRequest() {
      const sessionId = req.headers['mcp-session-id'] as string | undefined
      if (!sessionId || !transports[sessionId]) {
        httpSetTextResponse(res, 400, 'Invalid or missing session ID')
        return
      }

      const transport = transports[sessionId]
      await transport.handleRequest(req, res)
    }

    // Handle CORS preflight requests
    if (req.method === 'OPTIONS') {
      res.setHeader('Access-Control-Allow-Origin', '*')
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, mcp-session-id')
      res.statusCode = 200
      res.end()
      return
    }


    // Handle different request methods and paths
    if (match('POST', '/mcp') || match('POST', '/python/mcp')) {
      // Check for existing session ID
      const sessionId = req.headers['mcp-session-id'] as string | undefined
      let transport: StreamableHTTPServerTransport

      const body = await httpGetBody(req)

      if (sessionId && transports[sessionId]) {
        // Reuse existing transport
        transport = transports[sessionId]
      } else if (!sessionId && isInitializeRequest(body)) {
        // New initialization request
        transport = new StreamableHTTPServerTransport({
          sessionIdGenerator: () => randomUUID(),
          onsessioninitialized: (sessionId) => {
            // Store the transport by session ID
            transports[sessionId] = transport
          },
        })

        // Clean up transport when closed
        transport.onclose = () => {
          if (transport.sessionId) {
            delete transports[transport.sessionId]
          }
        }

        await mcpServer.connect(transport)
      } else {
        httpSetJsonResponse(res, 400, 'Bad Request: No valid session ID provided', -32000)
        return
      }

      // Handle the request
      await transport.handleRequest(req, res, body)
    } else if (match('GET', '/mcp') || match('GET', '/python/mcp')) {
      // Handle server-to-client notifications via SSE
      await handleSessionRequest()
    } else if (match('DELETE', '/mcp') || match('DELETE', '/python/mcp')) {
      // Handle requests for session termination
      await handleSessionRequest()
    } else if (pathMatch) {
      httpSetTextResponse(res, 405, 'Method not allowed')
    } else {
      httpSetTextResponse(res, 404, 'Page not found')
    }
  })

  server.listen(port, () => {
    console.log(
      `Running MCP Run Python version ${VERSION} with Streamable HTTP transport on port ${port}`,
    )
  })
}

/*
 * Run the MCP server using the SSE transport, e.g. over HTTP.
 */
function runSse(port: number) {
  const mcpServer = createServer()
  const transports: { [sessionId: string]: SSEServerTransport } = {}

  const server = http.createServer(async (req, res) => {
    const url = httpGetUrl(req)
    let pathMatch = false
    function match(method: string, path: string): boolean {
      if (url.pathname === path) {
        pathMatch = true
        return req.method === method
      }
      return false
    }

    if (match('GET', '/sse')) {
      const transport = new SSEServerTransport('/messages', res)
      transports[transport.sessionId] = transport
      res.on('close', () => {
        delete transports[transport.sessionId]
      })
      await mcpServer.connect(transport)
    } else if (match('POST', '/messages')) {
      const sessionId = url.searchParams.get('sessionId') ?? ''
      const transport = transports[sessionId]
      if (transport) {
        await transport.handlePostMessage(req, res)
      } else {
        httpSetTextResponse(res, 400, `No transport found for sessionId '${sessionId}'`)
      }
    } else if (pathMatch) {
      httpSetTextResponse(res, 405, 'Method not allowed')
    } else {
      httpSetTextResponse(res, 404, 'Page not found')
    }
  })

  server.listen(port, () => {
    console.log(
      `Running MCP Run Python version ${VERSION} with SSE transport on port ${port}`,
    )
  })
}

/*
 * Run the MCP server using the Stdio transport.
 */
async function runStdio() {
  const mcpServer = createServer()
  const transport = new StdioServerTransport()
  await mcpServer.connect(transport)
}

/*
 * Run pyodide to download packages which can otherwise interrupt the server
 */
async function warmup() {
  console.error(
    `Running warmup script for MCP Run Python version ${VERSION}...`,
  )
  const code = `
import numpy
a = numpy.array([1, 2, 3])
print('numpy array:', a)
a
`
  const result = await runCode([{
    name: 'warmup.py',
    content: code,
    active: true,
  }], (level, data) =>
    // use warn to avoid recursion since console.log is patched in runCode
    console.error(`${level}: ${data}`))
  console.log('Tool return value:')
  console.log(asXml(result))
  console.log('\nwarmup successful 🎉')
}

// list of log levels to use for level comparison
const LogLevels: LoggingLevel[] = [
  'debug',
  'info',
  'notice',
  'warning',
  'error',
  'critical',
  'alert',
  'emergency',
]

await main()
