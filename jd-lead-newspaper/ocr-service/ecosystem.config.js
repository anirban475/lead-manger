const workers = process.env.OCR_WORKERS || 4;
const timeout = process.env.OCR_WORKER_TIMEOUT || 360;

module.exports = {
  apps: [
    {
      name: 'ocr-service',
      script: 'gunicorn',
      args: `--bind 172.21.0.1:5050 --workers ${workers} --timeout ${timeout} app:app`,
      cwd: '/root/projects/lead-manger/jd-lead-newspaper/ocr-service',
      interpreter: 'none',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONUNBUFFERED: '1',
        OMP_THREAD_LIMIT: '1',
      },
    },
  ],
};
