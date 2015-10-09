package com.mantz_it.rfanalyzer;

import android.os.Environment;
import android.util.Log;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * <h1>RF Analyzer - Analyzer Processing Loop</h1>
 *
 * Module:      AnalyzerProcessingLoop.java
 * Description: This Thread will fetch samples from the incoming queue (provided by the scheduler),
 *              do the signal processing (fft) and then forward the result to the AnalyzerSurface at a
 *              fixed rate. It stabilises the rate at which the fft is generated to give the
 *              waterfall display a linear time scale.
 *
 * @author Dennis Mantz
 *
 * Copyright (C) 2014 Dennis Mantz
 * License: http://www.gnu.org/licenses/gpl.html GPL version 2 or higher
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
 */
public class AnalyzerProcessingLoop extends Thread {
	private int fftSize = 0;					// Size of the FFT
	private int frameRate = 10;					// Frames per Second
	private double load = 0;					// Time_for_processing_and_drawing / Time_per_Frame
	private boolean dynamicFrameRate = true;	// Turns on and off the automatic frame rate control
	private boolean stopRequested = true;		// Will stop the thread when set to true
	private float[] mag = null;					// Magnitude of the frequency spectrum

	private static final String LOGTAG = "AnalyzerProcessingLoop";
	private static final int MAX_FRAMERATE = 30;		// Upper limit for the automatic frame rate control
	private static final double LOW_THRESHOLD = 0.65;	// at every load value below this threshold we increase the frame rate
	private static final double HIGH_THRESHOLD = 0.85;	// at every load value above this threshold we decrease the frame rate

	private AnalyzerSurface view;
	private FFT fftBlock = null;
	private ArrayBlockingQueue<SamplePacket> inputQueue = null;		// queue that delivers sample packets
	private ArrayBlockingQueue<SamplePacket> returnQueue = null;	// queue to return unused buffers

	// File to output frame shots
	private long frameShotStart = 0;
	private long frameShotEnd = 0;
	private float[] shotFragment = null;
	private BufferedOutputStream frameOut = null;
	private File frameFile = null;

	/**
	 * Constructor. Will initialize the member attributes.
	 *
	 * @param view			reference to the AnalyzerSurface for drawing
	 * @param fftSize		Size of the FFT
	 * @param inputQueue	queue that delivers sample packets
	 * @param returnQueue	queue to return unused buffers
	 */
	public AnalyzerProcessingLoop(AnalyzerSurface view, int fftSize,
				ArrayBlockingQueue<SamplePacket> inputQueue, ArrayBlockingQueue<SamplePacket> returnQueue) {
		this.view = view;

		// Check if fftSize is a power of 2
		int order = (int)(Math.log(fftSize) / Math.log(2));
		if(fftSize != (1<<order))
			throw new IllegalArgumentException("FFT size must be power of 2");
		this.fftSize = fftSize;

		this.fftBlock = new FFT(fftSize);
		this.mag = new float[fftSize];
		this.inputQueue = inputQueue;
		this.returnQueue = returnQueue;
	}

	public int getFrameRate() {
		return frameRate;
	}

	public void setFrameShotEnd( long frameShotEnd ) { this.frameShotEnd = frameShotEnd; }

	public void setFrameRate(int frameRate) {
		this.frameRate = frameRate;
	}

	public boolean isDynamicFrameRate() {
		return dynamicFrameRate;
	}

	public void setDynamicFrameRate(boolean dynamicFrameRate) {
		this.dynamicFrameRate = dynamicFrameRate;
	}

	public int getFftSize() { return fftSize; }

	/**
	 * Will start the processing loop
	 */
	@Override
	public void start() {
		this.stopRequested = false;
		super.start();
	}

	/**
	 * Will set the stopRequested flag so that the processing loop will terminate
	 */
	public void stopLoop() {
		this.stopRequested = true;
	}

	/**
	 * @return true if loop is running; false if not.
	 */
	public boolean isRunning() {
		return !stopRequested;
	}

	@Override
	public void run() {
		Log.i(LOGTAG,"Processing loop started. (Thread: " + this.getName() + ")");
		// The enviroment variables used for filename.
		final String externalDir = Environment.getExternalStorageDirectory().getAbsolutePath();
		final String RECORDING_DIR = "RFAnalyzer";
		final SimpleDateFormat simpleDateFormat = new SimpleDateFormat("yyyy-MM-dd-HH-mm-ss", Locale.US);

		long startTime;		// timestamp when signal processing is started
		long sleepTime;		// time (in ms) to sleep before the next run to meet the frame rate
		long frequency;		// center frequency of the incoming samples
		int sampleRate;		// sample rate of the incoming samples
		int frameShot = 0;	// Whether it is taking frameShot;
		int pFrameShot = 0;	// Whether it was taking frameShot in last buffer.
									// Used to decide where to start and stop.

		while(!stopRequested) {
			// store the current timestamp
			startTime = System.currentTimeMillis();

			// fetch the next samples from the queue:
			SamplePacket samples;
			try {
				samples = inputQueue.poll(1000 / frameRate, TimeUnit.MILLISECONDS);
				if (samples == null) {
					Log.d(LOGTAG, "run: Timeout while waiting on input data. skip.");
					continue;
				}
			} catch (InterruptedException e) {
				Log.e(LOGTAG, "run: Interrupted while polling from input queue. stop.");
				this.stopLoop();
				break;
			}

			frequency = samples.getFrequency();
			sampleRate = samples.getSampleRate();
			frameShot = samples.getFrameShot();
			if (frameShot != 0) Log.i(LOGTAG, "FrameShot Open! Fre: " + frequency);

			// do the signal processing:
			this.doProcessing(samples);

			try {
				if (pFrameShot == 0 && frameShot != 0) {
					// Frame shot starts, create output file
					frameShotStart = frequency;
					frameFile = new File(externalDir + "/" + RECORDING_DIR + "/FrameShot_"
							+ simpleDateFormat.format(new Date()) + ".txt");
					frameFile.getParentFile().mkdir();    // Create directory if it does not yet exist
					frameOut = new BufferedOutputStream(new FileOutputStream(frameFile));

					if (frameOut != null) {
						// Put the start / end frequency on the first line.
						String firstLine = Long.toString(frameShotStart) + ' '
								+ Long.toString(this.frameShotEnd) + ' '
								+ Integer.toString(sampleRate) + '\n';
						frameOut.write(firstLine.getBytes());
					}
				}

				if (frameShot != 0 && frameOut != null) {
					// Put the data for this area into the file.
					int aSize = mag.length;
					// Make sure the output does not include the data out of range.
					if (frameShot == 2 && pFrameShot == 2) {
						Log.e(LOGTAG, "Error happened, two sequential 2 at " + frequency);
					} else {
						if (frameShot == 1 && pFrameShot == 1) {
							Log.e(LOGTAG, "Error happened, two Sequencial 1 at " + frequency);
						}
						if (frameShot == 1) {
							int startP = 0;
							int endP = aSize / 3;
							if (frequency - sampleRate / 2 < frameShotStart) {
								startP = (int) Math.floor((double)
										(frameShotStart - (frequency - sampleRate / 2)) * aSize / sampleRate);
							}
							if (frequency - sampleRate / 6 > frameShotEnd) {
								endP = aSize - (int) Math.floor((double)
										((frequency - sampleRate / 6) - frameShotEnd) * aSize / 3 / sampleRate);
							}
							if (startP < endP) {
								float[] outArray = Arrays.copyOfRange(mag, startP, endP);
								String outLine = Arrays.toString(outArray);
								outLine = outLine.substring(1, outLine.length() - 1) + '\n';
								frameOut.write(outLine.getBytes());
							}
							shotFragment = Arrays.copyOfRange(mag, aSize * 2 / 3, aSize);
						} else if (frameShot == 2) {
							int startP = 0;
							int endP = aSize;
							if (frequency - sampleRate / 2 < frameShotStart) {
								startP = (int) Math.floor((double)
										(frameShotStart - (frequency - sampleRate / 2)) * aSize / sampleRate);
							}
							if (frequency + sampleRate / 2 > frameShotEnd) {
								endP = aSize - (int) Math.floor((double)
										((frequency + sampleRate / 2) - frameShotEnd) * aSize / sampleRate);
							}
							float[] connectedArray = new float[aSize];
							System.arraycopy(mag, 0, connectedArray, 0, aSize * 2 / 3 - aSize / 3);
							System.arraycopy(shotFragment, 0, connectedArray, aSize*2/3 - aSize/3, shotFragment.length);
							System.arraycopy(mag, aSize - aSize / 3, connectedArray, aSize - aSize / 3, aSize / 3);
							float[] outArray = Arrays.copyOfRange(connectedArray, startP, endP);
							String outLine = Arrays.toString(outArray);
							outLine = outLine.substring(1, outLine.length() - 1) + '\n';
							frameOut.write(outLine.getBytes());
						}
					}
				}
			} catch (FileNotFoundException e) {
				Log.e(LOGTAG, "AnalyzerProcessingLoop: File not found: " + frameFile.getAbsolutePath());
			} catch (IOException e) {
				Log.e(LOGTAG, "run: Error while writing FrameOut: " + e.getMessage());
			}

			if (pFrameShot != 0 && frameShot == 0) {
				// Time to close the file
				try {
					frameOut.close();
					frameFile = null;
					frameOut = null;
				} catch (IOException e) {
					Log.e(LOGTAG, "run: Error while close FrameOut: " + e.getMessage());
				}
			}

			// return samples to the buffer pool
			returnQueue.offer(samples);

			// To improve the frame shot speed, close the display function while taking the shot
			if (frameShot == 0) {
				// Push the results on the surface:
				view.draw(mag, frequency, sampleRate, frameRate, load);

				// Calculate the remaining time in this frame (according to the frame rate) and sleep
				// for that time:
				sleepTime = (1000 / frameRate) - (System.currentTimeMillis() - startTime);
				try {
					if (sleepTime > 0) {
						// load = processing_time / frame_duration
						load = (System.currentTimeMillis() - startTime) / (1000.0 / frameRate);

						// Automatic frame rate control:
						if (dynamicFrameRate && load < LOW_THRESHOLD && frameRate < MAX_FRAMERATE)
							frameRate++;
						if (dynamicFrameRate && load > HIGH_THRESHOLD && frameRate > 1)
							frameRate--;

						//Log.d(LOGTAG,"FrameRate: " + frameRate + ";  Load: " + load + "; Sleep for " + sleepTime + "ms.");
						sleep(sleepTime);
					} else {
						// Automatic frame rate control:
						if (dynamicFrameRate && frameRate > 1)
							frameRate--;

						//Log.d(LOGTAG, "Couldn't meet requested frame rate!");
						load = 1;
					}
				} catch (Exception e) {
					Log.e(LOGTAG, "Error while calling sleep()");
				}
			}
			pFrameShot = frameShot;
		}
		this.stopRequested = true;
		Log.i(LOGTAG,"Processing loop stopped. (Thread: " + this.getName() + ")");
	}

	/**
	 * This method will do the signal processing (fft) on the given samples
	 *
	 * @param samples	input samples for the signal processing
	 */
	public void doProcessing(SamplePacket samples) {
		float[] re=samples.re(), im=samples.im();
		// Multiply the samples with a Window function:
		this.fftBlock.applyWindow(re, im);

		// Calculate the fft:
		this.fftBlock.fft(re, im);

		// Calculate the logarithmic magnitude:
		float realPower;
		float imagPower;
		int size = samples.size();
		for (int i = 0; i < size; i++) {
			// We have to flip both sides of the fft to draw it centered on the screen:
			int targetIndex = (i+size/2) % size;

			// Calc the magnitude = log(  re^2 + im^2  )
			// note that we still have to divide re and im by the fft size
			realPower = re[i]/fftSize;
			realPower = realPower * realPower;
			imagPower = im[i]/fftSize;
			imagPower = imagPower * imagPower;
			mag[targetIndex] = (float) (10* Math.log10(Math.sqrt(realPower + imagPower)));
		}
	}
}
