// Skill strings come straight from the LLM extractor with no consistent casing
// ("react", "React", "REACT", "rest apis", "REST APIs"). This gives each one a
// single canonical spelling for display. Kept in sync with the server-side copy
// in server/etl/skills.py — the ETL applies the same rules on ingest, so this is
// really a fallback for older rows.
//
// The rules are deliberately conservative: a word the model already capitalised
// is left untouched, so "DNS", "SaaS", "PyTorch", "Data structures and
// algorithms" all survive intact.

// Exact spellings for skills whose casing isn't just "capitalise the word".
const CANONICAL: Record<string, string> = {
  'javascript': 'JavaScript',
  'typescript': 'TypeScript',
  'nodejs': 'Node.js',
  'node.js': 'Node.js',
  'node': 'Node.js',
  'reactjs': 'React',
  'react.js': 'React',
  'react': 'React',
  'react native': 'React Native',
  'nextjs': 'Next.js',
  'next.js': 'Next.js',
  'vuejs': 'Vue.js',
  'vue.js': 'Vue.js',
  'vue': 'Vue.js',
  'angular': 'Angular',
  'redux': 'Redux',
  'graphql': 'GraphQL',
  'postgresql': 'PostgreSQL',
  'postgres': 'PostgreSQL',
  'mysql': 'MySQL',
  'nosql': 'NoSQL',
  'mongodb': 'MongoDB',
  'dynamodb': 'DynamoDB',
  'redis': 'Redis',
  'kafka': 'Kafka',
  'elasticsearch': 'Elasticsearch',
  'restful apis': 'REST APIs',
  'rest apis': 'REST APIs',
  'restful api': 'REST API',
  'rest api': 'REST API',
  'restful': 'REST',
  'ci/cd': 'CI/CD',
  'cicd': 'CI/CD',
  'tcp/udp': 'TCP/UDP',
  'tcp/ip': 'TCP/IP',
  'oauth': 'OAuth',
  'grpc': 'gRPC',
  'k8s': 'K8s',
  'devops': 'DevOps',
  'mlops': 'MLOps',
  'vxworks': 'VxWorks',
  'git': 'Git',
  'github': 'GitHub',
  'gitlab': 'GitLab',
  'jira': 'Jira',
  'linux': 'Linux',
  'unix': 'Unix',
  'docker': 'Docker',
  'kubernetes': 'Kubernetes',
  'jenkins': 'Jenkins',
  'terraform': 'Terraform',
  'ansible': 'Ansible',
  'nginx': 'nginx',
  'npm': 'npm',
  'webpack': 'webpack',
  'tcpdump': 'tcpdump',
  'ebpf': 'eBPF',
  'openai': 'OpenAI',
  'pytorch': 'PyTorch',
  'tensorflow': 'TensorFlow',
  'numpy': 'NumPy',
  'pandas': 'pandas',
  'scikit-learn': 'scikit-learn',
  'matplotlib': 'matplotlib',
  'fastapi': 'FastAPI',
  'django': 'Django',
  'flask': 'Flask',
  'spring': 'Spring',
  'spring boot': 'Spring Boot',
  '.net': '.NET',
  'dotnet': '.NET',
  'c++': 'C++',
  'c#': 'C#',
  'c/c++': 'C/C++',
  'f#': 'F#',
  'objective-c': 'Objective-C',
  'golang': 'Go',
  'kotlin': 'Kotlin',
  'scala': 'Scala',
  'swift': 'Swift',
  'rust': 'Rust',
  'ruby': 'Ruby',
  'ruby on rails': 'Ruby on Rails',
  'html/css': 'HTML/CSS',
  'ui/ux': 'UI/UX',
  'ms sql': 'MS SQL',
  'ms sql server': 'MS SQL Server',
  'ibm mq': 'IBM MQ',
  'opc ua': 'OPC UA',
  'iec 62304': 'IEC 62304',
  'soc 2': 'SOC 2',
  'iso 13485': 'ISO 13485',
  'iso 27001': 'ISO 27001',
  'saas': 'SaaS',
  'paas': 'PaaS',
  'iaas': 'IaaS',
  'ios': 'iOS',
  'macos': 'macOS',
}

// Standalone words to upper-case, with their exact display form so plurals
// ("APIs", "LLMs") keep the trailing lower-case "s".
const ACRONYMS: Record<string, string> = {}
for (const a of [
  'ai', 'ml', 'nlp', 'llm', 'api', 'sdk', 'cli', 'ui', 'ux', 'css', 'html',
  'sql', 'json', 'xml', 'yaml', 'http', 'https', 'dns', 'tcp', 'udp', 'rest',
  'rpc', 'aws', 'gcp', 'sap', 'crm', 'erp', 'etl', 'ci', 'cd', 'qa', 'seo',
  'ssr', 'orm', 'jwt', 'gpu', 'cpu', 'os', 'ide', 'oop', 'tdd', 'bdd', 'wpf',
  'sqs', 'sns', 'rdma', 'eda', 'cad', 'hil', 'sil', 'vpc', 'iam', 'ssl', 'tls',
  'ssh', 'vpn', 'cdn', 'wcag',
]) {
  ACRONYMS[a] = a.toUpperCase()
}
Object.assign(ACRONYMS, { apis: 'APIs', llms: 'LLMs', ids: 'IDs', sdks: 'SDKs' })

const HAS_UPPER = /[A-Z]/

export function formatSkill(raw: string): string {
  const skill = String(raw).replace(/\s+/g, ' ').trim()
  if (!skill) return skill

  const key = skill.toLowerCase()
  if (CANONICAL[key]) return CANONICAL[key]

  // A multi-word phrase the model shouted ("DISTRIBUTED SYSTEMS") — fold it so
  // it doesn't stay all-caps. Needs a word of 5+ letters so short all-caps
  // product names ("MS SQL", "AWS EC2") and acronym runs are left alone.
  const parts = skill.split(' ')
  const normalized =
    parts.length > 1 && skill === skill.toUpperCase() && parts.some(p => p.length >= 5)
      ? skill.toLowerCase()
      : skill

  return normalized
    .split(' ')
    .map((word, i) => {
      const lower = word.toLowerCase()
      if (CANONICAL[lower]) return CANONICAL[lower]
      if (ACRONYMS[lower]) return ACRONYMS[lower]
      if (HAS_UPPER.test(word)) return word // model already cased it
      if (i === 0) return lower.charAt(0).toUpperCase() + lower.slice(1)
      return lower
    })
    .join(' ')
}
