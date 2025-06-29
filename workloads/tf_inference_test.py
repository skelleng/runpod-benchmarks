#!/usr/bin/env python3
import tensorflow as tf, numpy as np, time
model = tf.keras.applications.MobileNetV2(weights=None, input_shape=(224,224,3))
# synthetic batch of 8 images
inp = np.random.rand(8,224,224,3).astype("float32")
start = time.time()
_ = model(inp, training=False)
print("TF inf:", time.time() - start)
